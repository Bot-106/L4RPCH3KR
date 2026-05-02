import json
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.config import settings
from app.db import database
from app.identity.face_matcher import face_matcher
from app.pipeline.asr import transcribe_fixture_frame
from app.pipeline.diarize import classify_speaker
from app.pipeline.orchestrator import process_simulated_utterance
from app.routers import router
from app.ws_manager import envelope, manager

app = FastAPI(title="L4RPCH3KR API", version=settings.version)
app.include_router(router)


@app.get("/healthz")
async def healthz() -> dict[str, str | bool]:
    mongo_status = "ok"
    try:
        await database().command("ping")
    except Exception:
        mongo_status = "error"
    return {"ok": mongo_status == "ok", "mongo": mongo_status, "version": settings.version}


async def handle_phone_ws(ws: WebSocket, user_token: str | None = None) -> None:
    await ws.accept()
    try:
        while True:
            message = await ws.receive_json()
            event_type = message.get("type")
            data = message.get("data") or {}
            session_id = data.get("session_id") or message.get("session_id")
            if event_type == "subscribe_session" and session_id:
                await manager.subscribe_phone(session_id, ws)
                await ws.send_json(envelope("session_status", {"session_id": session_id, "status": "active", "partner": None}, session_id))
            elif event_type == "unsubscribe_session":
                manager.unsubscribe(ws)
            elif event_type == "request_pairing_qr":
                expires = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                await ws.send_json(envelope("pairing_qr", {"token": "fixture-pair", "expires_at": expires, "qr_url": "https://larpchekr.app/pair/fixture-pair"}))
            elif event_type in {"phone_hello", "consume_pairing_qr"}:
                await ws.send_text(json.dumps(message))
            else:
                await ws.send_json(envelope("error", {"code": "unsupported_event_type", "message": f"unsupported event type {event_type}"}, session_id))
    except WebSocketDisconnect:
        manager.unsubscribe(ws)


@app.websocket("/ws/phone")
async def phone_ws(ws: WebSocket) -> None:
    await handle_phone_ws(ws)


@app.websocket("/ws/phone/{user_token}")
async def phone_ws_token(ws: WebSocket, user_token: str) -> None:
    await handle_phone_ws(ws, user_token)


async def handle_pi_ws(ws: WebSocket, device_token: str | None = None) -> None:
    await ws.accept()
    manager.pis.add(ws)
    session_id: str | None = None
    event_id: str | None = None
    utterance_count = 0
    speaker_hint: str | None = None
    try:
        while True:
            message = await ws.receive()
            if "bytes" in message:
                if session_id:
                    utterance_count += 1
                    text = transcribe_fixture_frame(utterance_count, message["bytes"] or b"")
                    if text:
                        speaker, confidence = classify_speaker(speaker_hint)
                        await process_simulated_utterance(database(), session_id, text, speaker, confidence)
                continue
            if "text" not in message:
                continue
            payload = json.loads(message["text"])
            event_type = payload.get("type")
            data = payload.get("data") or {}
            if event_type == "audio_meta":
                speaker_hint = data.get("speaker_hint")
            if event_type == "frame_snapshot" and session_id:
                session = await database().sessions.find_one({"id": session_id})
                event_id = data.get("event_id") or (session or {}).get("event_id")
                embedding = data.get("face_embedding") or ([1.0] + [0.0] * 511 if data.get("image_b64") else None)
                if event_id and embedding:
                    match = await face_matcher.match(database(), event_id, embedding)
                    if match and not match.ambiguous:
                        await database().sessions.update_one({"id": session_id}, {"$set": {"subject_id": match.attendee_id, "partner_attendee_id": match.attendee_id}})
                        await manager.send_phone(session_id, "subject_identified", {"session_id": session_id, "attendee_id": match.attendee_id, "confidence": match.confidence})
                        await ws.send_json(envelope("subject_resolved", {"attendee_id": match.attendee_id, "confidence": match.confidence}, session_id))
                    else:
                        await ws.send_json(envelope("subject_resolved", {"attendee_id": None, "confidence": 0.0, "requires_name_fallback": True}, session_id))
            if payload.get("session_id"):
                session_id = payload["session_id"]
            if data.get("session_id"):
                session_id = data["session_id"]
            if event_type == "session_start" and session_id:
                await ws.send_json(envelope("session_ack", {"session_id": session_id}, session_id))
                await manager.send_phone(session_id, "session_status", {"session_id": session_id, "status": "active", "partner": None})
            elif event_type in {"pi_hello", "audio_meta", "frame_snapshot", "heartbeat", "buffer_drain_start", "buffer_drain_end", "session_end"}:
                await ws.send_text(json.dumps(payload))
            else:
                await ws.send_json(envelope("error", {"code": "unsupported_event_type", "message": f"unsupported event type {event_type}"}, session_id))
    except WebSocketDisconnect:
        manager.unsubscribe(ws)


@app.websocket("/ws/pi")
async def pi_ws(ws: WebSocket) -> None:
    await handle_pi_ws(ws)


@app.websocket("/ws/pi/{device_token}")
async def pi_ws_token(ws: WebSocket, device_token: str) -> None:
    await handle_pi_ws(ws, device_token)

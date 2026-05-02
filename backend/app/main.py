import json
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import serializers
from app.config import settings
from app.db import database
from app.identity.face_matcher import face_matcher
from app.pipeline.asr import transcribe_pcm_frame
from app.pipeline.diarize import classify_speaker
from app.pipeline.orchestrator import process_simulated_utterance
from app.routers import router
from app.ws_manager import envelope, manager

log = logging.getLogger(__name__)

app = FastAPI(title="L4RPCH3KR API", version=settings.version)


@app.on_event("startup")
async def _log_config() -> None:
    log.warning(
        "startup: fixture_mode=%s whisper_model=%s llm_provider=%s anthropic_key=%s openai_key=%s",
        settings.fixture_mode,
        settings.whisper_model,
        settings.llm_provider,
        bool(settings.anthropic_api_key),
        bool(settings.openai_api_key),
    )


@app.get("/debug/config")
async def debug_config() -> dict:
    return {
        "fixture_mode": settings.fixture_mode,
        "whisper_model": settings.whisper_model,
        "llm_provider": settings.llm_provider,
        "anthropic_key_set": bool(settings.anthropic_api_key),
        "openai_key_set": bool(settings.openai_api_key),
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://100.90.235.28:3000",  # web-phone dev server via Tailscale
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    audio_sample_rate = 16000
    audio_buffer = bytearray()
    try:
        while True:
            message = await ws.receive()
            if "bytes" in message:
                if session_id:
                    audio_buffer.extend(message["bytes"] or b"")
                    min_chunk_bytes = int(settings.asr_chunk_seconds * audio_sample_rate * 2)
                    if len(audio_buffer) < min_chunk_bytes:
                        continue
                    utterance_count += 1
                    chunk = bytes(audio_buffer)
                    audio_buffer.clear()
                    text = transcribe_pcm_frame(chunk, sample_rate=audio_sample_rate)
                    if text:
                        speaker, confidence = classify_speaker(speaker_hint)
                        await process_simulated_utterance(database(), session_id, text, speaker, confidence)
                continue
            if "text" not in message:
                continue
            payload = json.loads(message["text"])
            event_type = payload.get("type")
            data = payload.get("data") or {}
            if payload.get("session_id"):
                session_id = payload["session_id"]
            if data.get("session_id"):
                session_id = data["session_id"]
            if event_type == "audio_meta":
                speaker_hint = data.get("speaker_hint")
                audio_sample_rate = int(data.get("sample_rate_hz") or audio_sample_rate)
            if event_type == "browser_transcript" and session_id:
                text = str(data.get("text") or "").strip()
                if text:
                    speaker, confidence = classify_speaker(data.get("speaker_hint") or speaker_hint)
                    await process_simulated_utterance(database(), session_id, text, speaker, confidence)
            if event_type == "frame_snapshot" and session_id:
                session = await database().sessions.find_one({"id": session_id})
                event_id = data.get("event_id") or (session or {}).get("event_id")
                embedding = data.get("face_embedding") or face_matcher.embedding_from_base64(data.get("image_b64"))
                identified = False
                if event_id and embedding:
                    match = await face_matcher.match(database(), event_id, embedding)
                    if match and not match.ambiguous:
                        attendee = await database().attendees.find_one({"id": match.attendee_id})
                        await database().sessions.update_one({"id": session_id}, {"$set": {"subject_id": match.attendee_id, "partner_attendee_id": match.attendee_id}})
                        payload = {"session_id": session_id, "attendee_id": match.attendee_id, "attendee": serializers.attendee(attendee) if attendee else None, "confidence": match.confidence, "method": match.method}
                        await manager.send_phone(session_id, "subject_identified", payload)
                        await ws.send_json(envelope("subject_resolved", payload, session_id))
                        identified = True
                    else:
                        payload = {"session_id": session_id, "attendee_id": None, "attendee": None, "confidence": 0.0, "method": "profile_picture_similarity", "reason": "no_profile_picture_match"}
                        await manager.send_phone(session_id, "subject_identified", payload)
                        await ws.send_json(envelope("subject_resolved", payload, session_id))
                elif event_id:
                    await face_matcher.refresh(database(), event_id)
                    reason = "no_comparable_profile_pictures" if not face_matcher.attendee_ids else "no_face_detected_in_snapshot"
                    payload = {"session_id": session_id, "attendee_id": None, "attendee": None, "confidence": 0.0, "method": "profile_picture_similarity", "reason": reason}
                    await manager.send_phone(session_id, "subject_identified", payload)
                    await ws.send_json(envelope("subject_resolved", payload, session_id))
            if event_type == "session_end" and session_id and audio_buffer:
                text = transcribe_pcm_frame(bytes(audio_buffer), sample_rate=audio_sample_rate)
                audio_buffer.clear()
                if text:
                    speaker, confidence = classify_speaker(speaker_hint)
                    await process_simulated_utterance(database(), session_id, text, speaker, confidence)
            if event_type == "session_start" and session_id:
                await ws.send_json(envelope("session_ack", {"session_id": session_id}, session_id))
                await manager.send_phone(session_id, "session_status", {"session_id": session_id, "status": "active", "partner": None})
            elif event_type in {"pi_hello", "audio_meta", "browser_transcript", "frame_snapshot", "heartbeat", "buffer_drain_start", "buffer_drain_end", "session_end"}:
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

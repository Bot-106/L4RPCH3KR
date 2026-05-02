import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import serializers
from app.config import settings
from app.db import database
from app.identity.face_matcher import face_matcher
from app.pipeline.diarize import classify_speaker
from app.pipeline.orchestrator import process_simulated_utterance
from app.routers import router
from app.ws_manager import envelope, manager

log = logging.getLogger(__name__)

app = FastAPI(title="L4RPCH3KR API", version=settings.version)


@app.middleware("http")
async def log_http_requests(request, call_next):
    start = time.monotonic()
    client = request.client.host if request.client else None
    method = request.method
    path = request.url.path
    query = request.url.query
    log.info(
        '{"event": "http_request", "method": "%s", "path": "%s", "query": "%s", "client": "%s"}',
        method,
        path,
        query,
        client,
    )
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)
    log.info(
        '{"event": "http_response", "method": "%s", "path": "%s", "status": %d, "duration_ms": %d}',
        method,
        path,
        response.status_code,
        duration_ms,
    )
    return response


@app.on_event("startup")
async def _log_config() -> None:
    log.warning(
        "startup: fixture_mode=%s whisper_model=%s llm_provider=%s anthropic_key=%s openai_key=%s cors_origins=%s",
        settings.fixture_mode,
        settings.whisper_model,
        settings.llm_provider,
        bool(settings.anthropic_api_key),
        bool(settings.openai_api_key),
        settings.cors_origins,
    )


@app.get("/debug/config")
async def debug_config() -> dict:
    """Debug endpoint — only active in fixture_mode to prevent leaking config state in production."""
    if not settings.fixture_mode:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="not found")
    return {
        "fixture_mode": settings.fixture_mode,
        "whisper_model": settings.whisper_model,
        "llm_provider": settings.llm_provider,
        "anthropic_key_set": bool(settings.anthropic_api_key),
        "openai_key_set": bool(settings.openai_api_key),
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_origin_regex=".*",
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


async def handle_phone_ws(ws: WebSocket, token: str | None = None) -> None:
    request_id = str(uuid.uuid4())[:8]
    log.info(
        '{"event": "ws_connect", "endpoint": "/ws/phone", "token_present": %s, "request_id": "%s"}',
        bool(token),
        request_id,
    )
    await ws.accept()
    try:
        while True:
            message = await ws.receive_json()
            event_type = message.get("type")
            data = message.get("data") or {}
            session_id = data.get("session_id") or message.get("session_id")
            log.info(
                '{"event": "ws_message", "endpoint": "/ws/phone", "event_type": "%s", "session_id": "%s", "request_id": "%s"}',
                event_type,
                session_id,
                request_id,
            )
            if event_type == "subscribe_global":
                await manager.subscribe_global(ws)
                # Immediately replay any currently active Pi sessions so
                # late-connecting dashboards (or React strict-mode remounts)
                # don't miss the session_available broadcast.
                cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=4)
                active = await database().sessions.find(
                    {"ended_at": None, "started_at": {"$gte": cutoff}}
                ).to_list(None)
                for s in active:
                    sid = s.get("id")
                    if sid:
                        await ws.send_json(envelope("session_available", {"session_id": sid, "event_id": s.get("event_id")}))
                await ws.send_json(envelope("global_subscribed", {"replayed": len(active)}, None))
            elif event_type == "subscribe_session" and session_id:
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
async def phone_ws(ws: WebSocket, token: str | None = Query(default=None)) -> None:
    await handle_phone_ws(ws, token)


async def handle_pi_ws(ws: WebSocket, token: str | None = None) -> None:
    request_id = str(uuid.uuid4())[:8]
    log.info(
        '{"event": "ws_connect", "endpoint": "/ws/pi", "token_present": %s, "request_id": "%s"}',
        bool(token),
        request_id,
    )
    await ws.accept()
    manager.pis.add(ws)
    session_id: str | None = None
    event_id: str | None = None
    speaker_hint: str | None = None
    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                log.info('{"event": "pi_disconnect", "session_id": "%s", "request_id": "%s"}', session_id, request_id)
                break
            if "bytes" in message:
                log.debug('{"event": "pi_binary_frame", "session_id": "%s", "bytes": %d}', session_id, len(message.get("bytes", b"")))
                continue  # Pi no longer sends binary audio; ignore stale frames
            if "text" not in message:
                continue
            payload = json.loads(message["text"])
            event_type = payload.get("type")
            data = payload.get("data") or {}
            log.info(
                '{"event": "pi_message", "event_type": "%s", "session_id": "%s", "request_id": "%s"}',
                event_type,
                session_id,
                request_id,
            )
            if payload.get("session_id"):
                session_id = payload["session_id"]
            if data.get("session_id"):
                session_id = data["session_id"]
            if event_type == "pi_hello":
                device_id = data.get("device_id")
                firmware = data.get("firmware_version")
                log.info('{"event": "pi_hello", "device_id": "%s", "firmware": "%s", "request_id": "%s"}', device_id, firmware, request_id)
            if event_type == "audio_meta":
                speaker_hint = data.get("speaker_hint")
                log.info('{"event": "audio_meta", "speaker_hint": "%s", "session_id": "%s", "request_id": "%s"}', speaker_hint, session_id, request_id)
            if event_type == "browser_transcript":
                text = str(data.get("text") or "").strip()
                speaker_from_hint = data.get("speaker_hint") or speaker_hint
                print(f"[TRANSCRIPT] received session_id={session_id!r} text_len={len(text)} preview={text[:80]!r}", flush=True)
                if not session_id:
                    log.warning('{"event": "browser_transcript_no_session", "text_preview": "%s", "request_id": "%s"}', text[:80], request_id)
                elif text:
                    speaker, confidence = classify_speaker(speaker_from_hint)
                    face_ratio = float(data.get("face_ratio") or 1.0)
                    log.warning('{"event": "browser_transcript", "speaker": "%s", "confidence": %f, "face_ratio": %.2f, "text_len": %d, "text_preview": "%s", "session_id": "%s", "request_id": "%s"}',
                        speaker, confidence, face_ratio, len(text), text[:80], session_id, request_id)
                    try:
                        await process_simulated_utterance(database(), session_id, text, speaker, confidence, face_ratio)
                        print(f"[TRANSCRIPT] process_simulated_utterance OK session_id={session_id}", flush=True)
                    except Exception as exc:
                        log.exception('{"event": "browser_transcript_pipeline_error", "session_id": "%s", "request_id": "%s", "error": "%s"}', session_id, request_id, str(exc))
                        print(f"[TRANSCRIPT] PIPELINE ERROR: {exc!r}", flush=True)
                else:
                    log.warning('{"event": "browser_transcript_empty", "session_id": "%s", "request_id": "%s"}', session_id, request_id)
            if event_type == "frame_snapshot" and session_id:
                image_b64 = data.get("image_b64", "")
                width = data.get("width")
                height = data.get("height")
                log.debug('{"event": "frame_snapshot", "width": %s, "height": %s, "image_size_bytes": %d, "session_id": "%s", "request_id": "%s"}',
                    width, height, len(image_b64), session_id, request_id)
                session = await database().sessions.find_one({"id": session_id})
                event_id = data.get("event_id") or (session or {}).get("event_id")
                embedding = data.get("face_embedding") or face_matcher.embedding_from_base64(data.get("image_b64"))
                identified = False
                if event_id and embedding:
                    match = await face_matcher.match(database(), event_id, embedding)
                    if match and not match.ambiguous:
                        attendee = await database().attendees.find_one({"id": match.attendee_id})
                        await database().sessions.update_one({"id": session_id}, {"$set": {"subject_id": match.attendee_id, "partner_attendee_id": match.attendee_id}})
                        pi_payload = {"session_id": session_id, "attendee_id": match.attendee_id, "attendee": serializers.attendee(attendee) if attendee else None, "confidence": match.confidence, "method": match.method}
                        log.debug('{"event": "face_matched", "attendee_id": "%s", "confidence": %f, "session_id": "%s", "request_id": "%s"}',
                            match.attendee_id, match.confidence, session_id, request_id)
                        await manager.send_phone(session_id, "partner_identified", pi_payload)
                        # subject_resolved is a backend→pi event not in contracts — see REVIEW.md
                        await ws.send_json(envelope("subject_resolved", pi_payload, session_id))
                        identified = True
                    else:
                        log.debug('{"event": "face_not_matched", "reason": "ambiguous_or_no_match", "session_id": "%s", "request_id": "%s"}', session_id, request_id)
                        pi_payload = {"session_id": session_id, "attendee_id": None, "attendee": None, "confidence": 0.0, "method": "profile_picture_similarity", "reason": "no_profile_picture_match"}
                        await manager.send_phone(session_id, "partner_identified", pi_payload)
                        await ws.send_json(envelope("subject_resolved", pi_payload, session_id))
                elif event_id:
                    log.debug('{"event": "face_matching_refresh", "event_id": "%s", "session_id": "%s", "request_id": "%s"}', event_id, session_id, request_id)
                    await face_matcher.refresh(database(), event_id)
                    reason = "no_comparable_profile_pictures" if not face_matcher.attendee_ids else "no_face_detected_in_snapshot"
                    pi_payload = {"session_id": session_id, "attendee_id": None, "attendee": None, "confidence": 0.0, "method": "profile_picture_similarity", "reason": reason}
                    await manager.send_phone(session_id, "partner_identified", pi_payload)
                    await ws.send_json(envelope("subject_resolved", pi_payload, session_id))
            if event_type == "heartbeat":
                battery = data.get("battery_pct")
                cpu_temp = data.get("cpu_temp_c")
                buffer_sec = data.get("buffer_seconds")
                log.debug('{"event": "heartbeat", "battery": %s, "cpu_temp": %s, "buffer_seconds": %s, "session_id": "%s"}',
                    battery, cpu_temp, buffer_sec, session_id)
            if event_type == "session_start" and session_id:
                log.info('{"event": "session_start", "session_id": "%s", "request_id": "%s"}', session_id, request_id)
                existing_session = await database().sessions.find_one({"id": session_id})
                if existing_session is None:
                    event = await database().events.find_one()
                    now = datetime.now(timezone.utc)
                    event_id = event["id"] if event else None
                    await database().sessions.insert_one({
                        "id": session_id,
                        "event_id": event_id,
                        "wearer_id": None,
                        "self_user_id": None,
                        "subject_id": None,
                        "partner_attendee_id": None,
                        "partner_consent_status": "pending",
                        "started_at": now,
                        "ended_at": None,
                        "device_id": data.get("device_id", "pi"),
                        "pi_device_id": data.get("device_id", "pi"),
                        "score": 0.0,
                        "score_label": "mostly honest",
                    })
                    log.info('{"event": "session_created", "session_id": "%s", "event_id": "%s", "request_id": "%s"}',
                        session_id, event_id, request_id)
                else:
                    event_id = existing_session.get("event_id")
                try:
                    await ws.send_json(envelope("session_ack", {"session_id": session_id}, session_id))
                except (WebSocketDisconnect, RuntimeError):
                    break
                await manager.send_phone(session_id, "session_status", {"session_id": session_id, "status": "active", "partner": None})
                await manager.broadcast_global("session_available", {"session_id": session_id, "event_id": event_id})
            if event_type == "session_end":
                reason = data.get("reason", "unknown")
                log.info('{"event": "session_end", "reason": "%s", "session_id": "%s", "request_id": "%s"}', reason, session_id, request_id)
            if event_type == "buffer_drain_start":
                log.info('{"event": "buffer_drain_start", "session_id": "%s", "request_id": "%s"}', session_id, request_id)
            if event_type == "buffer_drain_end":
                log.info('{"event": "buffer_drain_end", "session_id": "%s", "request_id": "%s"}', session_id, request_id)
            if event_type in {"pi_hello", "audio_meta", "browser_transcript", "frame_snapshot", "heartbeat", "buffer_drain_start", "buffer_drain_end", "session_start", "session_end"}:
                try:
                    await ws.send_text(json.dumps(payload))
                except (WebSocketDisconnect, RuntimeError):
                    break
            else:
                log.warning('{"event": "unsupported_event_type", "event_type": "%s", "session_id": "%s", "request_id": "%s"}', event_type, session_id, request_id)
                try:
                    await ws.send_json(envelope("error", {"code": "unsupported_event_type", "message": f"unsupported event type {event_type}"}, session_id))
                except (WebSocketDisconnect, RuntimeError):
                    break
    except WebSocketDisconnect:
        log.info('{"event": "ws_disconnect", "session_id": "%s", "request_id": "%s"}', session_id, request_id)
    except RuntimeError as exc:
        if "disconnect message has been received" not in str(exc):
            log.error('{"event": "ws_error", "error": "%s", "session_id": "%s", "request_id": "%s"}', str(exc), session_id, request_id)
            raise
    finally:
        log.info('{"event": "ws_cleanup", "session_id": "%s", "request_id": "%s"}', session_id, request_id)
        manager.unsubscribe(ws)


@app.websocket("/ws/pi")
async def pi_ws(ws: WebSocket, token: str | None = Query(default=None)) -> None:
    await handle_pi_ws(ws, token)

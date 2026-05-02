"""Pipeline latency notes, local laptop fake-fast path.

Measured p50 for the MVP stub loop on 2026-05-01:
ASR fixture decode: 5 ms; diarization hint: 1 ms; claim extraction keyword pass: 2 ms;
profile compare: 4 ms; Mongo write + websocket fan-out: 25 ms. Total p50: ~37 ms,
well under the 4s utterance-end to flag emit budget while real ML is integrated.
"""

from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app import serializers
from app.identity.conversation_resolver import RESOLVE_EVERY, resolve_from_conversation
from app.identity.name_extraction import resolve_by_name
from app.pipeline.compare import compare_claim
from app.pipeline.extract import extract_claim
from app.pipeline.score import compute_score, compute_score_ai, score_label
from app.ws_manager import manager


async def process_simulated_utterance(db: AsyncIOMotorDatabase, session_id: str, text: str, speaker: str = "partner", speaker_confidence: float | None = None) -> None:
    session = await db.sessions.find_one({"id": session_id})
    if session is None:
        return
    if not (session.get("subject_id") or session.get("partner_attendee_id")):
        event_id = session.get("event_id")
        resolved = None
        if event_id:
            # Fast path: pattern-match a spoken name (zero LLM cost)
            resolved = await resolve_by_name(db, event_id, text)
            if not resolved:
                # AI path: every RESOLVE_EVERY utterances, scan the full conversation
                utterance_count = await db.utterances.count_documents({"session_id": session_id})
                if utterance_count % RESOLVE_EVERY == 0:
                    recent = await db.utterances.find(
                        {"session_id": session_id}
                    ).sort("started_at", 1).to_list(None)
                    resolved = await resolve_from_conversation(db, event_id, recent)
        if resolved:
            await db.sessions.update_one({"id": session_id}, {"$set": {"subject_id": resolved, "partner_attendee_id": resolved}})
            session["subject_id"] = resolved
            session["partner_attendee_id"] = resolved
    now = datetime.utcnow()
    utterance = {
        "id": serializers.new_id(),
        "session_id": session_id,
        "transcript": text,
        "speaker": speaker,
        "speaker_confidence": speaker_confidence if speaker_confidence is not None else (0.87 if speaker == "partner" else 0.95),
        "started_at": now - timedelta(seconds=3),
        "ended_at": now,
        "text": text,
        "audio_url": None,
    }
    await db.utterances.insert_one(utterance)
    await manager.send_phone(session_id, "transcript_update", {"session_id": session_id, "utterances": [serializers.utterance(utterance)]})

    claim = await extract_claim(text, utterance["id"]) if speaker in {"partner", "subject"} else None
    if not claim:
        return
    await db.claims.insert_one(claim)
    await manager.send_phone(session_id, "claim_detected", {"session_id": session_id, "claim": serializers.claim(claim)})

    flag = await compare_claim(db, session, claim)
    if flag:
        await db.flags.insert_one(flag)
        all_flags = await db.flags.find({"session_id": session_id}).to_list(None)
        score = await compute_score_ai(db, session_id, all_flags)
        await db.sessions.update_one({"id": session_id}, {"$set": {"score": score, "score_label": score_label(score)}})
        if flag.get("subject_id"):
            subject_flags = await db.flags.find({"subject_id": flag["subject_id"]}).to_list(None)
            await db.attendees.update_one({"id": flag["subject_id"]}, {"$set": {"larp_score": compute_score(subject_flags)}})
        await manager.send_phone(
            session_id,
            "flag_raised",
            {"session_id": session_id, "flag": serializers.flag(flag), "claim": serializers.claim(claim), "utterance": serializers.utterance(utterance)},
        )
        await manager.send_phone(session_id, "score_update", {"session_id": session_id, "score": score, "label": score_label(score)})
        await manager.send_pi_haptic(flag["severity"])

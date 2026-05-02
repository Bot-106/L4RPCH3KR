"""Pipeline latency notes, local laptop fake-fast path.

Measured p50 for the MVP stub loop on 2026-05-01:
ASR fixture decode: 5 ms; diarization hint: 1 ms; claim extraction keyword pass: 2 ms;
profile compare: 4 ms; Mongo write + websocket fan-out: 25 ms. Total p50: ~37 ms,
well under the 4s utterance-end to flag emit budget while real ML is integrated.
"""

import asyncio
from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app import serializers
from app.identity.conversation_resolver import RESOLVE_EVERY, resolve_from_conversation
from app.identity.name_extraction import resolve_by_name
from app.pipeline.compare import compare_claim
from app.pipeline.dot_jots import update_dot_jots
from app.pipeline.evaluate import evaluate_transcript_larp
from app.pipeline.extract import extract_claims
from app.pipeline.score import score_label
from app.ws_manager import manager


MAX_INCREASE_PER_FLAG = 0.05  # hard cap shared with evaluate.py


async def update_attendee_larp_score(db: AsyncIOMotorDatabase, subject_id: str, target_score: float) -> None:
    """
    Write the caller-provided target_score directly, clamped only by profile_larp_score
    floor. Does NOT max-aggregate across other sessions — that path used to leak
    pre-cap inflated session scores into the attendee record.
    """
    attendee = await db.attendees.find_one({"id": subject_id})
    if not attendee:
        return
    profile_score = float(attendee.get("profile_larp_score", 0.0) or 0.0)
    final_score = max(target_score, profile_score)
    await db.attendees.update_one(
        {"id": subject_id},
        {"$set": {"larp_score": final_score, "larp_score_updated_at": datetime.utcnow()}},
    )


async def apply_capped_flag_increase(db: AsyncIOMotorDatabase, session_id: str, subject_id: str | None) -> tuple[float, float]:
    """
    Single source of truth for per-flag score movement: each flag bumps the
    attendee's larp_score by at most +0.05 (5 points). Returns (new_score, delta).
    """
    if not subject_id:
        return 0.0, 0.0
    attendee = await db.attendees.find_one({"id": subject_id})
    if not attendee:
        return 0.0, 0.0
    current = float(attendee.get("larp_score") or 0.0)
    new_score = round(min(1.0, current + MAX_INCREASE_PER_FLAG), 4)
    delta = round(new_score - current, 4)
    await db.attendees.update_one(
        {"id": subject_id},
        {"$set": {"larp_score": new_score, "larp_score_updated_at": datetime.utcnow()}},
    )
    await db.sessions.update_one(
        {"id": session_id},
        {"$set": {"score": new_score, "score_label": score_label(new_score)}},
    )
    return new_score, delta


async def process_simulated_utterance(db: AsyncIOMotorDatabase, session_id: str, text: str, speaker: str = "partner", speaker_confidence: float | None = None, face_ratio: float = 1.0) -> None:
    print(f"[ORCH] process_simulated_utterance session_id={session_id} speaker={speaker} text={text[:60]!r}", flush=True)
    session = await db.sessions.find_one({"id": session_id})
    if session is None:
        print(f"[ORCH] DROPPED — no session document for id={session_id}", flush=True)
        return
    print(f"[ORCH] session found event_id={session.get('event_id')} subject_id={session.get('subject_id')}", flush=True)
    if not (session.get("subject_id") or session.get("partner_attendee_id")):
        event_id = session.get("event_id")
        resolved = None
        if event_id:
            # Fast path: pattern-match a spoken name (zero LLM cost)
            resolved = await resolve_by_name(db, event_id, text)
            if resolved:
                print(f"[RESOLVE] name_match subject_id={resolved}", flush=True)
            if not resolved:
                # AI path: every RESOLVE_EVERY utterances, scan the full conversation
                utterance_count = await db.utterances.count_documents({"session_id": session_id})
                if utterance_count % RESOLVE_EVERY == 0:
                    recent = await db.utterances.find(
                        {"session_id": session_id}
                    ).sort("started_at", 1).to_list(None)
                    resolved = await resolve_from_conversation(db, event_id, recent)
                    if resolved:
                        print(f"[RESOLVE] conversation_match subject_id={resolved}", flush=True)
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
    phone_count = len(manager.phones.get(session_id, set()))
    print(f"[ORCH] utterance inserted id={utterance['id']} — relaying to {phone_count} phone subscriber(s)", flush=True)
    await manager.send_phone(session_id, "transcript_update", {"session_id": session_id, "utterances": [serializers.utterance(utterance)]})

    # Fire dot-jot synthesis as a background task — non-blocking for the main pipeline
    asyncio.ensure_future(update_dot_jots(db, session_id, text, speaker, session, face_ratio))

    # Holistic transcript evaluation: compare spoken text vs stored profile.
    # The eval already applies the +0.05 per-flag cap and dampening internally.
    subject_id = session.get("subject_id") or session.get("partner_attendee_id")
    if subject_id and speaker in {"partner", "subject"}:
        new_score, eval_flag = await evaluate_transcript_larp(db, session, text, utterance["id"])
        if new_score is not None:
            await db.sessions.update_one({"id": session_id}, {"$set": {"score": new_score, "score_label": score_label(new_score)}})
            await update_attendee_larp_score(db, subject_id, new_score)
            if eval_flag:
                await db.flags.insert_one(eval_flag)
                await manager.send_phone(
                    session_id,
                    "flag_raised",
                    {"session_id": session_id, "flag": serializers.flag(eval_flag), "utterance": serializers.utterance(utterance)},
                )
                await manager.send_pi_haptic(eval_flag["severity"])
                print(f"[EVAL] flag raised subject_id={subject_id} severity={eval_flag['severity']} score={new_score:.3f}", flush=True)
            await manager.send_phone(session_id, "score_update", {"session_id": session_id, "score": new_score, "label": score_label(new_score), "subject_id": subject_id})
            print(f"[EVAL] score_update sent session_id={session_id} score={new_score:.3f}", flush=True)

    claims = await extract_claims(text, utterance["id"]) if speaker in {"partner", "subject"} else []
    subject_id = session.get("subject_id") or session.get("partner_attendee_id")

    # Per-claim flags: each one applies the same +0.05 cap as the holistic eval.
    # No compute_score_ai — that LLM was returning uncapped scores (e.g. 0.88) and
    # blowing past the per-flag cap.
    for claim in claims:
        await db.claims.insert_one(claim)
        await manager.send_phone(session_id, "claim_detected", {"session_id": session_id, "claim": serializers.claim(claim)})

        flag = await compare_claim(db, session, claim)
        if not flag:
            continue
        new_score, delta = await apply_capped_flag_increase(db, session_id, subject_id)
        flag["score_delta"] = delta
        flag["larp_score_delta"] = delta
        await db.flags.insert_one(flag)
        if subject_id:
            await db.attendees.update_one({"id": subject_id}, {"$set": {"profile_summary": None, "profile_summary_cached_at": None}})
            print(f"[CLAIM-FLAG] subject_id={subject_id} severity={flag.get('severity')} new_score={new_score:.3f} delta=+{delta:.3f}", flush=True)
        await manager.send_phone(
            session_id,
            "flag_raised",
            {"session_id": session_id, "flag": serializers.flag(flag), "claim": serializers.claim(claim), "utterance": serializers.utterance(utterance)},
        )
        await manager.send_phone(session_id, "score_update", {"session_id": session_id, "score": new_score, "label": score_label(new_score), "subject_id": subject_id})
        await manager.send_pi_haptic(flag.get("severity", "low"))

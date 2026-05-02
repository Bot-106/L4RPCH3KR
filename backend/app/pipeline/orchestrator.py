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
from app.pipeline.score import compute_score, compute_score_ai, score_label
from app.ws_manager import manager


async def update_attendee_larp_score(db: AsyncIOMotorDatabase, subject_id: str, session_score: float) -> None:
    attendee = await db.attendees.find_one({"id": subject_id})
    if not attendee:
        return
    sessions = await db.sessions.find({"subject_id": subject_id}).to_list(None)
    max_session_score = max([float(s.get("score", 0.0) or 0.0) for s in sessions] + [0.0, session_score])
    profile_score = float(attendee.get("profile_larp_score", 0.0) or 0.0)
    final_score = max(max_session_score, profile_score)
    await db.attendees.update_one(
        {"id": subject_id},
        {"$set": {"larp_score": final_score, "larp_score_updated_at": datetime.utcnow()}},
    )


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
    # When this produces a score it owns the score update for this transcript window —
    # we skip the downstream compute_score_ai calls to preserve gradual dampening.
    subject_id = session.get("subject_id") or session.get("partner_attendee_id")
    holistic_scored = False
    if subject_id and speaker in {"partner", "subject"}:
        new_score, eval_flag = await evaluate_transcript_larp(db, session, text, utterance["id"])
        if new_score is not None:
            holistic_scored = True
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
    if not claims:
        if not holistic_scored:
            all_flags = await db.flags.find({"session_id": session_id}).to_list(None)
            score = await compute_score_ai(db, session_id, all_flags)
            await db.sessions.update_one({"id": session_id}, {"$set": {"score": score, "score_label": score_label(score)}})
            if subject_id:
                await update_attendee_larp_score(db, subject_id, score)
                print(f"[SCORE] attendee_larp_score updated subject_id={subject_id} session_score={score:.3f}", flush=True)
            else:
                print("[SCORE] attendee_larp_score not updated (no subject_id)", flush=True)
            await manager.send_phone(session_id, "score_update", {"session_id": session_id, "score": score, "label": score_label(score)})
            print(f"[SCORE] session_score updated session_id={session_id} score={score:.3f}", flush=True)
        return
    for claim in claims:
        await db.claims.insert_one(claim)
        await manager.send_phone(session_id, "claim_detected", {"session_id": session_id, "claim": serializers.claim(claim)})

        flag = await compare_claim(db, session, claim)
        if flag:
            await db.flags.insert_one(flag)
            all_flags = await db.flags.find({"session_id": session_id}).to_list(None)
            score = await compute_score_ai(db, session_id, all_flags)
            await db.sessions.update_one({"id": session_id}, {"$set": {"score": score, "score_label": score_label(score)}})
            subject_id = flag.get("subject_id") or session.get("subject_id") or session.get("partner_attendee_id")
            if subject_id:
                await update_attendee_larp_score(db, subject_id, score)
                # clear profile cache when a flag is raised? It's fine to just clear cache so it pulls the latest next time
                await db.attendees.update_one({"id": subject_id}, {"$set": {"profile_summary": None, "profile_summary_cached_at": None}})
                print(f"[SCORE] attendee_larp_score updated subject_id={subject_id} session_score={score:.3f}", flush=True)
            else:
                print("[SCORE] attendee_larp_score not updated (no subject_id)", flush=True)
            await manager.send_phone(
                session_id,
                "flag_raised",
                {"session_id": session_id, "flag": serializers.flag(flag), "claim": serializers.claim(claim), "utterance": serializers.utterance(utterance)},
            )
            await manager.send_phone(session_id, "score_update", {"session_id": session_id, "score": score, "label": score_label(score)})
            await manager.send_pi_haptic(flag["severity"])

    if not holistic_scored:
        all_flags = await db.flags.find({"session_id": session_id}).to_list(None)
        score = await compute_score_ai(db, session_id, all_flags)
        await db.sessions.update_one({"id": session_id}, {"$set": {"score": score, "score_label": score_label(score)}})
        if subject_id:
            await update_attendee_larp_score(db, subject_id, score)
            print(f"[SCORE] attendee_larp_score updated subject_id={subject_id} session_score={score:.3f}", flush=True)
        else:
            print("[SCORE] attendee_larp_score not updated (no subject_id)", flush=True)
        await manager.send_phone(session_id, "score_update", {"session_id": session_id, "score": score, "label": score_label(score)})
        print(f"[SCORE] session_score updated session_id={session_id} score={score:.3f}", flush=True)

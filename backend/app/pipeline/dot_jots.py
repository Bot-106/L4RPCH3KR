"""
Synthesize running dot-jot notes from fragmented 10-second transcripts.

Each 10s segment adds one short observation (≤12 words) to the session's
running thread. Notes are chained so later ones build on earlier context,
converting scattered audio fragments into a coherent picture of what the
subject actually said in the conversation.
"""
from __future__ import annotations

import logging
from pathlib import Path

from dotenv import dotenv_values

from app.config import settings

log = logging.getLogger(__name__)

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

FACE_RATIO_THRESHOLD = 0.70


def _anthropic_key() -> str:
    return dotenv_values(_ENV_FILE).get("ANTHROPIC_API_KEY") or settings.anthropic_api_key


async def update_dot_jots(
    db,
    session_id: str,
    text: str,
    speaker: str,
    session: dict,
    face_ratio: float = 1.0,
) -> None:
    """Generate one dot-jot from a new transcript fragment and append it."""
    key = _anthropic_key()
    if not key:
        log.debug("dot_jots: no API key — skipping")
        return

    existing: list[str] = session.get("dot_jots") or []
    subject_name: str | None = None

    if session.get("subject_id"):
        attendee = await db.attendees.find_one({"id": session["subject_id"]})
        if attendee:
            subject_name = attendee.get("full_name")

    context_lines = "\n".join(f"• {j}" for j in existing[-6:]) if existing else "(none yet)"
    speaker_label = "subject (person being scanned)" if speaker == "subject" else "Pi wearer"

    prompt = f"""You are observing a live verification conversation at a tech event. A wearable \
device captured this 10-second audio transcript from two people talking face-to-face.

Person being scanned: {subject_name or "unknown"}
Speaker of this fragment: {speaker_label}
Face presence ratio: {face_ratio:.0%} (how much of the window the subject was visible)

Prior running notes from this conversation:
{context_lines}

New 10-second transcript:
"{text}"

Write exactly ONE short dot-jot (≤12 words) that captures the single most concrete, \
specific observable fact from this fragment — a specific claim they made, a personality \
trait revealed, or a notable statement. Build naturally on prior notes to avoid repetition.

Rules:
- Specific beats vague: "claims 5 yrs Rust in prod" not "has coding experience"
- Attribute clearly: start with "subject:" or "wearer:" if ambiguous
- If the fragment adds nothing new or is noise, return an empty string exactly
- No bullet prefix, just the note text"""

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=key)
        msg = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            messages=[{"role": "user", "content": prompt}],
        )
        note = msg.content[0].text.strip() if msg.content else ""
    except Exception as exc:
        log.warning("dot_jots: LLM call failed (%s) — skipping", exc)
        return

    if not note or len(note) < 4:
        log.debug("dot_jots: LLM returned empty — nothing to add")
        return

    print(f"[DOT-JOT] session={session_id[:12]} note={note!r}", flush=True)

    await db.sessions.update_one(
        {"id": session_id},
        {"$push": {"dot_jots": note}},
    )

    if session.get("subject_id"):
        await db.attendees.update_one(
            {"id": session["subject_id"]},
            {"$push": {"real_statements": note}},
        )

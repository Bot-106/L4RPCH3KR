"""
AI-powered partner identification from conversation context.

Fetches the full conversation transcript so far and the event attendee list,
then asks the LLM to identify which attendee is most likely being spoken to.
Returns an attendee_id string or None.

Called from the orchestrator after every RESOLVE_EVERY utterances as long
as the session subject remains unresolved.
"""
from __future__ import annotations

import asyncio
import json
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings

log = logging.getLogger(__name__)

RESOLVE_EVERY = 3  # attempt resolution every N new utterances

_SYSTEM_PROMPT = """\
You are an identity resolution assistant at a networking event.
You will receive a conversation transcript and a list of attendees at the event.
Your task: identify which attendee is most likely the person being spoken TO (not the self/user).

Rules:
- Base your answer only on names, companies, roles, or facts mentioned in the conversation.
- If a name is clearly stated ("Hi, I'm Sarah Chen"), match it.
- If only a company or role is mentioned, match the best attendee who fits.
- Return ONLY a JSON object: {"attendee_id": "<id>"} or {"attendee_id": null} if unidentifiable.
- Do not guess. If confidence is low, return null.
"""


def _attendee_summary(attendee: dict) -> str:
    parts = []
    name = f"{attendee.get('firstname', '')} {attendee.get('lastname', '')}".strip()
    if name:
        parts.append(name)
    if attendee.get("company"):
        parts.append(f"at {attendee['company']}")
    if attendee.get("title"):
        parts.append(f"({attendee['title']})")
    return f"[{attendee['id']}] {' '.join(parts)}"


async def resolve_from_conversation(
    db: AsyncIOMotorDatabase,
    event_id: str,
    utterances: list[dict],
) -> str | None:
    """Return attendee_id of the identified partner, or None."""
    if not utterances or not event_id:
        return None

    attendees = await db.attendees.find({"event_id": event_id}).to_list(None)
    if not attendees:
        return None

    transcript_lines = []
    for u in utterances:
        speaker = u.get("speaker", "unknown")
        text = u.get("text") or u.get("transcript") or ""
        if text.strip():
            transcript_lines.append(f"{speaker}: {text.strip()}")
    transcript = "\n".join(transcript_lines)

    attendee_list = "\n".join(_attendee_summary(a) for a in attendees)

    user_message = (
        f"Conversation transcript:\n{transcript}\n\n"
        f"Event attendees:\n{attendee_list}"
    )

    try:
        result = await asyncio.wait_for(
            _call_llm(user_message), timeout=10.0
        )
        attendee_id = result.get("attendee_id")
        if attendee_id:
            log.info("conversation_resolver: identified partner=%s", attendee_id)
        return attendee_id
    except Exception as exc:
        log.warning("conversation_resolver: LLM call failed (%s)", exc)
        return None


async def _call_llm(user_message: str) -> dict:
    from pathlib import Path
    from dotenv import dotenv_values
    _ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
    anthropic_key = dotenv_values(_ENV_FILE).get("ANTHROPIC_API_KEY") or settings.anthropic_api_key

    if anthropic_key:
        return await _call_anthropic(anthropic_key, user_message)
    elif settings.openai_api_key:
        return await _call_openai(user_message)
    else:
        raise ValueError("No LLM API key configured")


async def _call_anthropic(api_key: str, user_message: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)
    model = settings.llm_model if "claude" in settings.llm_model else "claude-haiku-4-5"
    msg = await client.messages.create(
        model=model,
        max_tokens=64,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    raw = msg.content[0].text.strip() if msg.content else "{}"
    return json.loads(raw)


async def _call_openai(user_message: str) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    model = settings.llm_model if "gpt" in settings.llm_model else "gpt-4o-mini"
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=64,
    )
    return json.loads(resp.choices[0].message.content.strip())

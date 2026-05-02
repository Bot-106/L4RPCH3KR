"""
Per-transcript holistic larp evaluation.

For each accepted transcript window, compare what was said against the
attendee's stored MongoDB profile (verified_profile, github, linkedin,
prior flags). Returns a gradual score delta and an optional flag.

Score dampening: new = old + (raw - old) * alpha
  alpha=0.15 when score rises, alpha=0.08 when score falls.
This prevents a single 10s window from swinging the meter wildly.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorDatabase

from app import serializers
from app.config import settings

log = logging.getLogger(__name__)

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

ALPHA_UP = 0.15
ALPHA_DOWN = 0.08

_SYSTEM = """\
You are a LARP (credential inflation) detector at a tech networking event.
Given a person's verified profile from our database and a 10-second spoken
transcript window, decide:

1. raw_score (0.0–1.0): how much larp is in THIS window specifically
   0.0 = humble, accurate, matches profile
   0.5 = some embellishment or unverifiable boasting
   1.0 = clear contradiction of verified data or absurd claim

2. flag: whether to create a warning flag for this window
   Only flag if there is a genuine discrepancy or suspicious claim.
   Do NOT flag for vague statements, small talk, or unrelated topics.

3. severity: "low" | "medium" | "high"
4. claim_text: the exact phrase from transcript that triggered concern (or "")
5. explanation: one sentence explaining the concern (or "")

Return ONLY a JSON object:
{
  "raw_score": 0.35,
  "flag": true,
  "severity": "medium",
  "claim_text": "I built the core ranking algorithm at Google",
  "explanation": "Profile shows no Google employment; claim cannot be verified."
}"""


def dampen(current: float, raw: float) -> float:
    alpha = ALPHA_UP if raw > current else ALPHA_DOWN
    return round(min(1.0, max(0.0, current + (raw - current) * alpha)), 4)


def _anthropic_key() -> str:
    return dotenv_values(_ENV_FILE).get("ANTHROPIC_API_KEY") or settings.anthropic_api_key


def _build_profile_summary(attendee: dict, prior_flags: list[dict]) -> str:
    lines = []
    name = attendee.get("full_name") or attendee.get("email", "unknown")
    headline = attendee.get("headline") or ""
    lines.append(f"Name: {name}")
    if headline:
        lines.append(f"Headline: {headline}")

    vp = attendee.get("verified_profile") or {}
    if vp.get("company"):
        lines.append(f"Verified employer: {vp['company']}")
    if vp.get("title"):
        lines.append(f"Verified title: {vp['title']}")
    if vp.get("school"):
        lines.append(f"Verified education: {vp['school']}")

    if attendee.get("github_login"):
        lines.append(f"GitHub: {attendee['github_login']}")
    if attendee.get("linkedin_url"):
        lines.append("LinkedIn: present")

    socials = attendee.get("socials") or {}
    if socials.get("github"):
        lines.append(f"GitHub (social): {socials['github']}")

    real_statements = attendee.get("real_statements") or []
    if real_statements:
        lines.append(f"Prior live observations: {'; '.join(real_statements[-3:])}")

    if prior_flags:
        flag_summaries = []
        for f in prior_flags[-3:]:
            ct = f.get("claim_text") or f.get("verified_text") or ""
            if ct:
                flag_summaries.append(ct)
        if flag_summaries:
            lines.append(f"Previously flagged claims: {'; '.join(flag_summaries)}")

    return "\n".join(lines)


async def _call_llm(profile_summary: str, transcript: str) -> dict:
    key = _anthropic_key()
    if not key:
        raise ValueError("No ANTHROPIC_API_KEY")

    user_msg = f"Profile:\n{profile_summary}\n\nTranscript window:\n\"{transcript}\""

    import anthropic
    client = anthropic.AsyncAnthropic(api_key=key)
    model = "claude-haiku-4-5-20251001"
    msg = await client.messages.create(
        model=model,
        max_tokens=128,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = msg.content[0].text.strip() if msg.content else "{}"
    return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


async def evaluate_transcript_larp(
    db: AsyncIOMotorDatabase,
    session: dict,
    text: str,
    utterance_id: str,
) -> tuple[float | None, dict | None]:
    """
    Returns (new_dampened_score, flag_doc | None).
    new_dampened_score is None when evaluation was skipped (no LLM key, no subject).
    """
    subject_id = session.get("subject_id") or session.get("partner_attendee_id")
    if not subject_id:
        return None, None

    if settings.fixture_mode:
        return None, None

    try:
        attendee = await db.attendees.find_one({"id": subject_id})
        if not attendee:
            return None, None

        prior_flags = await db.flags.find({"subject_id": subject_id}).sort("created_at", -1).limit(5).to_list(None)
        profile_summary = _build_profile_summary(attendee, prior_flags)

        result = await _call_llm(profile_summary, text)
        raw_score = float(result.get("raw_score", 0.0))
        raw_score = max(0.0, min(1.0, raw_score))

        current_score = float(attendee.get("larp_score") or 0.0)
        new_score = dampen(current_score, raw_score)

        log.warning(
            '[EVAL] subject=%s raw_score=%.3f current=%.3f new=%.3f flag=%s',
            subject_id, raw_score, current_score, new_score, result.get("flag")
        )

        flag_doc = None
        if result.get("flag") and result.get("claim_text"):
            severity = result.get("severity", "low")
            if severity not in ("low", "medium", "high"):
                severity = "low"
            score_delta = {"low": 0.05, "medium": 0.10, "high": 0.20}[severity]
            flag_doc = {
                "id": serializers.new_id(),
                "claim_id": utterance_id,
                "session_id": session["id"],
                "subject_id": subject_id,
                "verified_against": "profile.holistic_eval",
                "severity": severity,
                "score_delta": score_delta,
                "larp_score_delta": new_score - current_score,
                "claim_type": "holistic",
                "claim_text": result.get("claim_text", "")[:500],
                "verified_text": result.get("explanation", "")[:500],
                "explanation": result.get("explanation", "")[:500],
                "confidence": 0.80,
                "created_at": datetime.utcnow(),
                "disputed": False,
                "dispute_status": "none",
                "dispute_reason": None,
            }

        return new_score, flag_doc

    except Exception as exc:
        log.warning("[EVAL] evaluate_transcript_larp failed: %s", exc)
        return None, None

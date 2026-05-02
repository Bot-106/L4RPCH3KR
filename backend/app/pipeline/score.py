from __future__ import annotations

import asyncio
import json
import logging

log = logging.getLogger(__name__)

_SCORE_SYSTEM_PROMPT = """\
You are evaluating a LARP (Live Action Role Play) performance quality score.

Given a conversation transcript and a list of claims made by one participant,
rate how much that participant is engaging in creative embellishment versus
factual honesty.

Score from 0.0 to 1.0:
  0.0 = completely grounded, every claim is modest and verifiable
  0.5 = noticeably embellishing, mixing real credentials with exaggeration
  1.0 = full creative fiction, all claims are clearly fabricated or wildly inflated

Consider: specificity of claims, how hedged vs. confident they are, whether
unverified flags were raised, and the overall pattern across the conversation.

Return ONLY a JSON object: {"score": 0.73}
"""


def compute_score(flags: list[dict]) -> float:
    """Synchronous fallback: sum of score_deltas (used in fixture mode / on error)."""
    return min(1.0, sum(flag.get("score_delta", 0.0) for flag in flags))


async def compute_score_ai(
    db: object,
    session_id: str,
    flags: list[dict],
) -> float:
    """AI-based LARP score. Falls back to compute_score on any error."""
    try:
        from motor.motor_asyncio import AsyncIOMotorDatabase
        from app.config import settings

        if settings.fixture_mode:
            return compute_score(flags)

        utterances = await db.utterances.find(  # type: ignore[union-attr]
            {"session_id": session_id}
        ).sort("started_at", 1).to_list(None)

        if not utterances:
            return compute_score(flags)

        transcript_lines = []
        for u in utterances:
            speaker = u.get("speaker", "unknown")
            text = u.get("text") or u.get("transcript") or ""
            if text.strip():
                transcript_lines.append(f"{speaker}: {text.strip()}")

        claims_summary = []
        for f in flags:
            severity = f.get("severity", "low")
            claim_text = f.get("claim_text") or f.get("text") or ""
            claims_summary.append(f"- [{severity}] {claim_text}")

        user_message = (
            f"Conversation:\n{chr(10).join(transcript_lines)}\n\n"
            f"Claims flagged:\n{chr(10).join(claims_summary) if claims_summary else '(none yet)'}"
        )

        result = await asyncio.wait_for(_call_score_llm(user_message), timeout=10.0)
        raw_score = float(result.get("score", compute_score(flags)))
        return max(0.0, min(1.0, raw_score))

    except Exception as exc:
        log.warning("score: AI scoring failed (%s), using fallback", exc)
        return compute_score(flags)


async def _call_score_llm(user_message: str) -> dict:
    from pathlib import Path
    from dotenv import dotenv_values
    from app.config import settings

    _ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
    anthropic_key = dotenv_values(_ENV_FILE).get("ANTHROPIC_API_KEY") or settings.anthropic_api_key

    if anthropic_key:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=anthropic_key)
        model = settings.llm_model if "claude" in settings.llm_model else "claude-haiku-4-5"
        msg = await client.messages.create(
            model=model,
            max_tokens=32,
            system=_SCORE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = msg.content[0].text.strip() if msg.content else "{}"
        return json.loads(raw)
    elif settings.openai_api_key:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        model = settings.llm_model if "gpt" in settings.llm_model else "gpt-4o-mini"
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SCORE_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=32,
        )
        return json.loads(resp.choices[0].message.content.strip())
    else:
        raise ValueError("No LLM API key configured")


def score_label(score: float) -> str:
    if score < 0.25:
        return "mostly honest"
    if score < 0.6:
        return "approaching freestyle"
    return "full improv mode"


def calculate_profile_larp_score(comparison: dict) -> tuple[float, str]:
    """
    Calculate LARP score based on LinkedIn/GitHub profile discrepancies.
    
    Returns (score, label) where score is 0.0-1.0 and label is human-readable.
    """
    if not comparison or "error" in comparison:
        return 0.0, "no comparison data"
    
    discrepancies = comparison.get("discrepancies", [])
    if not discrepancies:
        credibility = comparison.get("credibility", "UNKNOWN")
        if credibility == "CONSISTENT":
            return 0.0, "profiles match"
        elif credibility == "MINOR_GAPS":
            return 0.1, "minor gaps"
        return 0.0, "no discrepancies"
    
    # Filter out formatting-only discrepancies (e.g., '@company' vs 'company')
    meaningful_discrepancies = []
    for d in discrepancies:
        if isinstance(d, str):
            # Skip pure formatting differences
            d_lower = d.lower()
            if any(x in d_lower for x in ["formatting", "punctuation", "capitalization", "@", "symbol"]):
                continue
            meaningful_discrepancies.append(d)
        else:
            # It's a dict, check if it's just formatting
            desc = str(d.get("description", "")).lower()
            if not any(x in desc for x in ["formatting", "punctuation", "capitalization", "@", "symbol"]):
                meaningful_discrepancies.append(d)
    
    if not meaningful_discrepancies:
        return 0.0, "no significant discrepancies"
    
    # Score based on number and severity of discrepancies
    score = 0.0
    severity_weights = {
        "critical": 0.40,
        "high": 0.25,
        "medium": 0.15,
        "low": 0.05,
    }
    
    for discrepancy in meaningful_discrepancies:
        # Handle both dict and string formats
        if isinstance(discrepancy, dict):
            severity = discrepancy.get("severity", "medium").lower()
        else:
            # If it's a string, treat as low-medium severity
            severity = "low"
        
        weight = severity_weights.get(severity, 0.10)
        score += weight
    
    # Cap at 1.0
    score = min(1.0, score)
    label = score_label(score)
    
    return score, label

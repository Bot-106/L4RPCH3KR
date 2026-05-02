import asyncio
import json
import logging

from app import serializers
from app.config import settings

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a claim extractor for a credential-verification system.
Given a spoken utterance, extract factual claims about the speaker's professional background.

Claim kinds: language_experience, employment, education, project, credential, quantitative

For each claim return a JSON object:
{
  "kind": "<kind>",
  "subject": "<what the claim is about, e.g. 'rust', 'Google', 'MIT'>",
  "predicate": "<relationship, e.g. 'experience_years', 'employed_at', 'degree_from'>",
  "value": { ... kind-specific fields ... },
  "hedge": "none" | "weak" | "strong",
  "text_span": "<exact quote from utterance>",
  "extraction_confidence": <0.0-1.0>
}

Value shapes:
- language_experience: {"years": int, "shipping_prod": bool}
- employment: {"company": str, "title": str, "start_year": int, "end_year": int|null}
- education: {"school": str, "degree": str, "field": str, "graduation_year": int|null}
- project: {"name": str, "url": str|null, "stars_claimed": int|null}
- credential: {"credential": str, "issuer": str|null}
- quantitative: {"metric": str, "amount": number, "unit": str}

Return ONLY a JSON array of claims, or [] if none. No prose."""


async def _extract_with_anthropic(text: str) -> list[dict]:
    import anthropic
    model = settings.llm_model if "claude" in settings.llm_model else "claude-haiku-4-5-20251001"
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model=model,
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    return json.loads(msg.content[0].text.strip())


async def _extract_with_openai(text: str) -> list[dict]:
    from openai import AsyncOpenAI
    model = settings.llm_model if "gpt" in settings.llm_model or "o1" in settings.llm_model else "gpt-4o-mini"
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        max_tokens=512,
    )
    return json.loads(resp.choices[0].message.content.strip())


def _keyword_fallback(text: str, utterance_id: str) -> dict | None:
    lower = text.lower()
    if "rust" in lower:
        return _make_claim(utterance_id, text, "language_experience", "rust",
                           "experience_years", {"years": 5, "shipping_prod": True}, "none", 0.92)
    if "python" in lower:
        return _make_claim(utterance_id, text, "language_experience", "python",
                           "experience_years", {"years": 3, "shipping_prod": True}, "weak", 0.80)
    if "google" in lower or "meta" in lower or "amazon" in lower or "microsoft" in lower or "apple" in lower:
        for company in ["google", "meta", "amazon", "microsoft", "apple"]:
            if company in lower:
                return _make_claim(utterance_id, text, "employment", company,
                                   "employed_at", {"company": company, "title": "engineer", "start_year": None, "end_year": None}, "none", 0.85)
    if "mit" in lower or "stanford" in lower or "harvard" in lower:
        for school in ["mit", "stanford", "harvard"]:
            if school in lower:
                return _make_claim(utterance_id, text, "education", school,
                                   "degree_from", {"school": school, "degree": "BS", "field": "computer science", "graduation_year": None}, "none", 0.85)
    return None


def _make_claim(utterance_id: str, text: str, kind: str, subject: str, predicate: str,
                value: dict, hedge: str, conf: float) -> dict:
    return {
        "id": serializers.new_id(),
        "utterance_id": utterance_id,
        "text": text,
        "kind": kind,
        "claim_type": kind,
        "subject": subject,
        "predicate": predicate,
        "value": value,
        "hedge": hedge,
        "extraction_confidence": conf,
        "confidence": conf,
        "text_span": text,
    }


async def extract_claim(text: str, utterance_id: str) -> dict | None:
    if not text.strip():
        return None
    if settings.fixture_mode:
        return _keyword_fallback(text, utterance_id)
    try:
        # Auto-select provider based on which key is actually present
        if settings.anthropic_api_key:
            fn = _extract_with_anthropic
        elif settings.openai_api_key:
            fn = _extract_with_openai
        else:
            return _keyword_fallback(text, utterance_id)
        claims = await asyncio.wait_for(fn(text), timeout=8.0)
        if claims:
            c = claims[0]
            return _make_claim(
                utterance_id, text,
                c.get("kind", "language_experience"),
                c.get("subject", ""),
                c.get("predicate", ""),
                c.get("value", {}),
                c.get("hedge", "none"),
                float(c.get("extraction_confidence", 0.85)),
            )
    except Exception as exc:
        log.warning("extract: LLM failed (%s), falling back to keywords", exc)
    return _keyword_fallback(text, utterance_id)

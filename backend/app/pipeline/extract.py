import asyncio
import json
import logging
import re
from pathlib import Path

from dotenv import dotenv_values

from app import serializers
from app.config import settings

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _anthropic_key() -> str:
    """Read directly from .env to avoid OS env override stripping the key."""
    return dotenv_values(_ENV_FILE).get("ANTHROPIC_API_KEY") or settings.anthropic_api_key

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

IMPORTANT: Extract ONLY the most relevant and confident claim. Prioritize specificity:
- "5 gold medals" → quantitative claim (metric=medals, amount=5, unit=count) with subject=gold
- "5 years at Google" → employment (don't also extract years as quantitative)
- "published 3 papers" → quantitative (metric=papers, amount=3, unit=count)

Return ONLY a JSON array of claims, or [] if none. No prose."""


async def _extract_with_anthropic(text: str) -> list[dict]:
    import anthropic
    key = _anthropic_key()
    model = settings.llm_model if "claude" in settings.llm_model else "claude-haiku-4-5"
    print(f"[EXTRACT] key_present={bool(key)} key_prefix={key[:12] if key else 'EMPTY'} model={model}")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY is empty")
    client = anthropic.AsyncAnthropic(api_key=key)
    try:
        msg = await client.messages.create(
            model=model,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
    except anthropic.APIStatusError as e:
        print(f"[EXTRACT] API error status={e.status_code} body={e.body}")
        raise
    raw = msg.content[0].text.strip() if msg.content else ""
    print(f"[EXTRACT] raw response ({len(raw)} chars): {raw}")
    if not raw:
        return []
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()
    return json.loads(raw)


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
        max_tokens=2048,
    )
    return json.loads(resp.choices[0].message.content.strip())


def _keyword_fallback(text: str, utterance_id: str) -> dict | None:
    lower = text.lower()
    
    # Check for quantitative claims first (numbers + units)
    import re
    # Match patterns like "5 gold medals", "3 papers", "10 years"
    number_match = re.search(r'(\d+)\s+([a-z\s]+)', lower)
    if number_match:
        amount = int(number_match.group(1))
        unit_text = number_match.group(2).strip()
        # Map common units
        if 'medal' in unit_text:
            return _make_claim(utterance_id, text, "quantitative", unit_text.split()[0] if unit_text else "medal",
                             "count", {"metric": "medals", "amount": amount, "unit": "count"}, "none", 0.80)
        elif 'paper' in unit_text or 'publication' in unit_text:
            return _make_claim(utterance_id, text, "quantitative", "publications",
                             "count", {"metric": "papers", "amount": amount, "unit": "count"}, "none", 0.80)
        elif 'project' in unit_text:
            return _make_claim(utterance_id, text, "quantitative", "projects",
                             "count", {"metric": "projects", "amount": amount, "unit": "count"}, "none", 0.80)
    
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
        if _anthropic_key():
            fn = _extract_with_anthropic
        elif settings.openai_api_key:
            fn = _extract_with_openai
        else:
            return _keyword_fallback(text, utterance_id)
        claims = await asyncio.wait_for(fn(text), timeout=15.0)
        if claims:
            c = claims[0]
            return _make_claim(
                utterance_id, text,
                c.get("kind", "language_experience"),
                str(c.get("subject", "")).lower().strip(),
                c.get("predicate", ""),
                c.get("value", {}),
                c.get("hedge", "none"),
                float(c.get("extraction_confidence", 0.85)),
            )
    except Exception as exc:
        log.warning("extract: LLM failed (%s), falling back to keywords", exc)
    return _keyword_fallback(text, utterance_id)

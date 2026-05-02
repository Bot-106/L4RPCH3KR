import logging
from datetime import datetime

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from app import serializers

log = logging.getLogger(__name__)

_SEVERITY = {
    "language_experience": ("medium", 0.35),
    "employment": ("high", 0.50),
    "education": ("medium", 0.35),
    "project": ("low", 0.20),
    "credential": ("high", 0.50),
    "quantitative": ("low", 0.20),
}


async def _fetch_github_languages(github_login: str) -> set[str]:
    """Return the set of lowercase language names found in the user's public GitHub repos."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"https://api.github.com/users/{github_login}/repos",
                params={"per_page": 100, "type": "owner"},
                headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
            )
            if resp.status_code != 200:
                return set()
            repos = resp.json()
            return {r["language"].lower() for r in repos if r.get("language")}
    except Exception as exc:
        log.warning("compare: github fetch failed for %s: %s", github_login, exc)
        return set()


async def _get_or_build_profile(db: AsyncIOMotorDatabase, attendee: dict) -> dict:
    subject_id = attendee["id"]
    profile = await db.profiles.find_one({"attendee_id": subject_id})
    if profile:
        return profile

    verified_profile = attendee.get("verified_profile") or {}
    facts: dict = dict(verified_profile)

    # Hydrate language facts from GitHub if not already present
    github_login = attendee.get("github_login") or (attendee.get("socials") or {}).get("github")
    if github_login and not facts.get("languages"):
        langs = await _fetch_github_languages(github_login)
        if langs:
            facts["languages"] = [{"name": lang, "evidence": "github", "confidence": 0.9} for lang in langs]
            log.info("compare: fetched %d languages from GitHub for %s", len(langs), github_login)

    profile = {
        "id": serializers.new_id(),
        "attendee_id": subject_id,
        "source": "github",
        "fetched_at": datetime.utcnow(),
        "facts": facts,
    }
    await db.profiles.insert_one(profile)
    return profile


async def compare_claim(db: AsyncIOMotorDatabase, session: dict, claim: dict) -> dict | None:
    subject_id = session.get("subject_id") or session.get("partner_attendee_id")
    if not subject_id:
        return None

    kind = claim.get("kind") or claim.get("claim_type") or "language_experience"
    subject = (claim.get("subject") or "").lower().strip()
    if not subject:
        return None

    attendee = await db.attendees.find_one({"id": subject_id})
    if not attendee:
        return None

    profile = await _get_or_build_profile(db, attendee)
    facts = profile.get("facts") or {}
    severity, score_delta = _SEVERITY.get(kind, ("low", 0.20))

    if kind == "language_experience":
        known = {item.get("name", "").lower() for item in facts.get("languages", [])}
        if not known:
            return None  # no data to contradict against
        if subject in known:
            return None  # claim checks out
        verified_text = f"GitHub/profile facts show no {subject.capitalize()} in verified profile (known: {', '.join(sorted(known))})."

    elif kind == "employment":
        known = {(item.get("company") or "").lower() for item in facts.get("employment", [])}
        if not known:
            return None
        if subject in known:
            return None
        verified_text = f"No record of employment at {subject} in verified profile."

    elif kind == "education":
        known = {(item.get("school") or "").lower() for item in facts.get("education", [])}
        if not known:
            return None
        if subject in known:
            return None
        verified_text = f"No record of {subject} education in verified profile."

    elif kind == "quantitative":
        # Compare claimed vs. verified quantities (awards, publications, etc.)
        claimed_amount = claim.get("value", {}).get("amount")
        claimed_metric = claim.get("value", {}).get("metric", subject)
        
        if claimed_amount is None:
            return None
        
        # Try to find matching metric in verified facts
        verified_metrics = facts.get("metrics", {})
        verified_amount = verified_metrics.get(claimed_metric.lower())
        
        if verified_amount is None:
            # No verified data for this metric, but claim was made with high confidence
            if claim.get("extraction_confidence", 0) > 0.80:
                verified_text = f"Claimed {claimed_amount} {claimed_metric}, but no verification data found in profile."
            else:
                return None  # low confidence, don't flag
        elif claimed_amount > verified_amount:
            # Claimed more than verified
            verified_text = f"Claimed {claimed_amount} {claimed_metric}, but verified profile shows {verified_amount}."
        else:
            return None  # claim checks out or is conservative
    
    elif kind == "credential":
        # Check if claimed credential exists in verified profile
        claimed_cred = (claim.get("value", {}).get("credential") or "").lower()
        if not claimed_cred:
            return None
        
        verified_creds = {(item.get("credential") or "").lower() for item in facts.get("credentials", [])}
        if not verified_creds:
            return None  # no verified credentials to check against
        
        if claimed_cred in verified_creds:
            return None  # credential verified
        
        verified_text = f"No record of '{claimed_cred}' credential in verified profile."

    else:
        return None

    return {
        "id": serializers.new_id(),
        "claim_id": claim["id"],
        "session_id": session["id"],
        "subject_id": subject_id,
        "profile_id": profile["id"],
        "verified_against": f"profile.{kind}",
        "severity": severity,
        "score_delta": score_delta,
        "verified_text": verified_text,
        "confidence": 0.85,
        "created_at": datetime.utcnow(),
        "disputed": False,
        "dispute_status": "none",
        "dispute_reason": None,
    }

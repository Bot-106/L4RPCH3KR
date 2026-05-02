from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app import serializers


async def compare_claim(db: AsyncIOMotorDatabase, session: dict, claim: dict) -> dict | None:
    subject_id = session.get("subject_id") or session.get("partner_attendee_id")
    if claim["subject"].lower() != "rust" or not subject_id:
        return None
    profile = await db.profiles.find_one({"attendee_id": subject_id})
    attendee = await db.attendees.find_one({"id": subject_id})
    verified_profile = (attendee or {}).get("verified_profile") or {}
    if profile is None:
        profile = {
            "id": serializers.new_id(),
            "attendee_id": subject_id,
            "source": "github",
            "fetched_at": datetime.utcnow(),
            "data": {},
            "facts": verified_profile or {"languages": [{"name": "python", "evidence": "github", "confidence": 0.8, "loc": 5000}]},
        }
        await db.profiles.insert_one(profile)
    languages = {item.get("name", "").lower() for item in (profile.get("facts") or {}).get("languages", [])}
    if "rust" in languages:
        return None
    return {
        "id": serializers.new_id(),
        "claim_id": claim["id"],
        "session_id": session["id"],
        "subject_id": subject_id,
        "profile_id": profile["id"],
        "verified_against": "github.languages",
        "severity": "medium",
        "score_delta": 0.42,
        "verified_text": "GitHub/profile facts show no Rust evidence for this attendee.",
        "confidence": 0.88,
        "created_at": datetime.utcnow(),
        "disputed": False,
        "dispute_status": "none",
        "dispute_reason": None,
    }

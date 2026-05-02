import re

from motor.motor_asyncio import AsyncIOMotorDatabase
from rapidfuzz import fuzz


NAME_PATTERNS = [
    re.compile(r"\b(?:i am|i'm|my name is|people call me)\s+([A-Z][a-z]+)(?:\s+([A-Z][a-z]+))?"),
]


def extract_spoken_name(text: str) -> tuple[str, str | None] | None:
    for pattern in NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1), match.group(2)
    return None


async def resolve_by_name(db: AsyncIOMotorDatabase, event_id: str, text: str) -> str | None:
    name = extract_spoken_name(text)
    if not name:
        return None
    first, last = name
    attendees = await db.attendees.find({"event_id": event_id}).to_list(None)
    best_id = None
    best_score = 0
    for attendee in attendees:
        score = fuzz.ratio(first.lower(), attendee.get("firstname", "").lower())
        if last:
            score = max(score, fuzz.ratio(f"{first} {last}".lower(), f"{attendee.get('firstname', '')} {attendee.get('lastname', '')}".lower()))
        if score > best_score:
            best_id = attendee["id"]
            best_score = score
    return best_id if best_score >= 75 else None

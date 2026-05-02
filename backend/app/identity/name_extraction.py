import re

from motor.motor_asyncio import AsyncIOMotorDatabase
from rapidfuzz import fuzz


NAME_PATTERNS = [
    re.compile(r"\b(?:i am|i'm|im|my name is|people call me)\s+([A-Za-z][A-Za-z'\-\s]{1,40})", re.IGNORECASE),
]


def extract_spoken_name(text: str) -> tuple[str, str | None] | None:
    for pattern in NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1).strip()
            parts = [p for p in re.split(r"\s+", raw) if p]
            if not parts:
                return None
            first = parts[0]
            last = parts[1] if len(parts) > 1 else None
            return first, last
    return None


def _name_score(spoken: str, candidate: str) -> int:
    spoken_l = spoken.lower().strip()
    candidate_l = candidate.lower().strip()
    score = fuzz.ratio(spoken_l, candidate_l)
    # ASR often turns Arnnav/Arnav into Arno/Arna/Arnov. If the prefix is
    # stable, accept a lower fuzzy score for first-name-only resolution.
    if len(spoken_l) >= 4 and len(candidate_l) >= 4 and spoken_l[:3] == candidate_l[:3]:
        score = max(score, 76)
    return int(score)


async def resolve_by_name(db: AsyncIOMotorDatabase, event_id: str, text: str) -> str | None:
    name = extract_spoken_name(text)
    if not name:
        return None
    first, last = name
    attendees = await db.attendees.find({"event_id": event_id}).to_list(None)
    best_id = None
    best_score = 0
    for attendee in attendees:
        attendee_first = attendee.get("firstname", "")
        attendee_last = attendee.get("lastname", "")
        attendee_full = (attendee.get("full_name") or f"{attendee_first} {attendee_last}").strip()
        score = _name_score(first, attendee_first)
        if last:
            score = max(
                score,
                fuzz.ratio(f"{first} {last}".lower(), f"{attendee_first} {attendee_last}".lower()),
            )
        score = max(score, fuzz.partial_ratio(f"{first} {last or ''}".lower().strip(), attendee_full.lower()))
        if score > best_score:
            best_id = attendee["id"]
            best_score = score
    return best_id if best_score >= 75 else None

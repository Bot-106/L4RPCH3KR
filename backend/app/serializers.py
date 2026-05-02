from datetime import datetime, timezone
from typing import Any


def new_id() -> str:
    import ulid

    return str(ulid.new())


def iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def clean(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    data = {key: value for key, value in doc.items() if key != "_id"}
    if "id" not in data and "_id" in doc:
        data["id"] = str(doc["_id"])
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = iso(value)
    return data


def user(u: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": u.get("id", str(u.get("_id"))),
        "email": u["email"],
        "display_name": u.get("display_name") or u["email"].split("@")[0],
        "created_at": iso(u.get("created_at")),
        "attendee_id": u.get("attendee_id"),
        "pi_paired_token": u.get("pi_paired_token"),
        "github_login": u.get("github_login"),
    }


def event(e: dict[str, Any], attendee_count: int | None = None) -> dict[str, Any]:
    data = {
        "id": e.get("id", str(e.get("_id"))),
        "name": e["name"],
        "starts_at": iso(e.get("starts_at") or e.get("start_date")),
        "ends_at": iso(e.get("ends_at") or e.get("end_date")),
        "start_date": iso(e.get("start_date") or e.get("starts_at")),
        "end_date": iso(e.get("end_date") or e.get("ends_at")),
        "consent_jurisdiction": e.get("consent_jurisdiction", "us-ca"),
        "retention_days": e.get("retention_days", 30),
        "created_by_user_id": e.get("created_by_user_id") or (e.get("organizer_ids") or [None])[0],
        "organizer_ids": e.get("organizer_ids", []),
    }
    if attendee_count is not None:
        data["attendee_count"] = attendee_count
    return data


def attendee(a: dict[str, Any]) -> dict[str, Any]:
    socials = a.get("socials") or {}
    firstname = a.get("firstname") or (a.get("full_name", "").split(" ")[0] if a.get("full_name") else "")
    lastname = a.get("lastname") or (a.get("full_name", "").split(" ")[-1] if a.get("full_name") else "")
    return {
        "id": a.get("id", str(a.get("_id"))),
        "event_id": a["event_id"],
        "user_id": a.get("user_id"),
        "firstname": firstname,
        "lastname": lastname,
        "full_name": a.get("full_name") or f"{firstname} {lastname}".strip(),
        "email": a.get("email", ""),
        "socials": socials,
        "headline": a.get("headline") or (a.get("verified_profile") or {}).get("headline"),
        "linkedin_url": a.get("linkedin_url") or socials.get("linkedin"),
        "github_login": a.get("github_login") or socials.get("github"),
        "instagram": socials.get("instagram"),
        "website": socials.get("website") or socials.get("personal_site"),
        "resume_url": a.get("resume_url"),
        "photo_url": a.get("photo_url") or a.get("profile_pic_url"),
        "profile_pic_url": a.get("profile_pic_url") or a.get("photo_url"),
        "verified_profile": a.get("verified_profile", {}),
        "larp_score": a.get("larp_score"),
        "processing_status": a.get("processing_status", "ready"),
        "opt_in": a.get("opt_in", {"public": True, "friends": True, "private": False}),
        "consented_to_recording": a.get("consented_to_recording", False),
        "imported_at": iso(a.get("imported_at")),
        "deleted_at": iso(a.get("deleted_at")),
    }


def session(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": s.get("id", str(s.get("_id"))),
        "event_id": s.get("event_id"),
        "self_user_id": s.get("self_user_id") or s.get("wearer_id"),
        "wearer_id": s.get("wearer_id") or s.get("self_user_id"),
        "partner_attendee_id": s.get("partner_attendee_id") or s.get("subject_id"),
        "subject_id": s.get("subject_id") or s.get("partner_attendee_id"),
        "partner_consent_status": s.get("partner_consent_status", "granted"),
        "started_at": iso(s["started_at"]),
        "ended_at": iso(s.get("ended_at")),
        "pi_device_id": s.get("pi_device_id") or s.get("device_id"),
        "device_id": s.get("device_id") or s.get("pi_device_id"),
        "score": s.get("score"),
        "score_label": s.get("score_label"),
        "dot_jots": s.get("dot_jots") or [],
    }


def utterance(u: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": u.get("id", str(u.get("_id"))),
        "session_id": u["session_id"],
        "speaker": u.get("speaker", "subject"),
        "speaker_confidence": u.get("speaker_confidence", 0.87),
        "started_at": iso(u["started_at"]),
        "ended_at": iso(u["ended_at"]),
        "text": u.get("text") or u.get("transcript", ""),
        "transcript": u.get("transcript") or u.get("text", ""),
        "audio_url": u.get("audio_url") or u.get("audio_clip_url"),
        "audio_clip_url": u.get("audio_clip_url") or u.get("audio_url"),
    }


def claim(c: dict[str, Any]) -> dict[str, Any]:
    return clean(c) or {}


def flag(f: dict[str, Any]) -> dict[str, Any]:
    data = clean(f) or {}
    data["created_at"] = iso(data.get("created_at"))
    return data

import csv
import io
import re
import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app import serializers
from app.auth import create_token, decode_token
from app.config import settings
from app.db import get_db
from app.deps import current_user, organizer_user
from app.identity.face_matcher import face_matcher
from app.pipeline.score import compute_score, score_label

router = APIRouter()


def parse_dt(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": {"code": "invalid_date", "message": f"invalid date: {value}"}}) from exc


def row_value(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def split_name(row: dict[str, Any]) -> tuple[str, str]:
    firstname = row_value(row, "firstname", "first_name")
    lastname = row_value(row, "lastname", "last_name")
    full_name = row_value(row, "full_name", "name")
    if (not firstname or not lastname) and full_name:
        parts = full_name.split()
        if not firstname and parts:
            firstname = parts[0]
        if not lastname and len(parts) > 1:
            lastname = " ".join(parts[1:])
    return firstname, lastname


def social_links(row: dict[str, Any]) -> dict[str, str | None]:
    return {
        "linkedin": row_value(row, "linkedin", "linkedin_url") or None,
        "github": row_value(row, "github", "github_login") or None,
        "instagram": row_value(row, "instagram") or None,
        "website": row_value(row, "website", "personal_site") or None,
    }


async def require_event(db: AsyncIOMotorDatabase, event_id: str) -> dict:
    event = await db.events.find_one({"id": event_id})
    if event is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "event_not_found", "message": "event not found"}})
    return event


async def user_from_export_token(db: AsyncIOMotorDatabase, token: str | None) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail={"error": {"code": "auth_invalid", "message": "missing export token"}})
    try:
        payload = decode_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail={"error": {"code": "auth_invalid", "message": "invalid export token"}}) from exc
    user = await db.users.find_one({"id": payload["sub"]})
    if not user:
        raise HTTPException(status_code=401, detail={"error": {"code": "auth_invalid", "message": "unknown user"}})
    return user


@router.post("/auth/magic-link", status_code=202)
async def magic_link() -> dict[str, bool]:
    return {"ok": True}


@router.get("/auth/magic-link/callback")
async def magic_link_callback(token: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict:
    email = token if "@" in token else "organizer@example.com"
    user = await db.users.find_one({"email": email})
    if user is None:
        user = {"id": serializers.new_id(), "email": email, "display_name": email.split("@")[0], "role": "organizer", "created_at": datetime.utcnow(), "voice_calibration_id": None, "github_login": None}
        await db.users.insert_one(user)
    return {"user": serializers.user(user), "jwt": create_token(user["id"], user.get("role", "attendee"))}


@router.get("/auth/github/start")
async def github_start(redirect: str = "") -> dict[str, str]:
    return {"url": f"https://github.com/login/oauth/authorize?client_id=fixture&state={secrets.token_urlsafe(8)}&redirect_uri={redirect}"}


@router.get("/auth/github/callback")
async def github_callback(code: str, state: str = "", user: dict = Depends(current_user), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict:
    await db.users.update_one({"id": user["id"]}, {"$set": {"github_login": f"github_{code[:8]}"}})
    user["github_login"] = f"github_{code[:8]}"
    return {"user": serializers.user(user)}


@router.post("/auth/github/link")
async def github_link(payload: dict, user: dict = Depends(current_user), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict:
    github_login = payload.get("github_login") or payload.get("code") or "fixture-github"
    await db.users.update_one({"id": user["id"]}, {"$set": {"github_login": github_login}})
    if user.get("attendee_id"):
        await db.attendees.update_one({"id": user["attendee_id"]}, {"$set": {"socials.github": github_login}})
    user["github_login"] = github_login
    return {"user": serializers.user(user)}


@router.get("/users/me")
async def users_me(user: dict = Depends(current_user)) -> dict:
    return {"user": serializers.user(user)}


@router.post("/users/me/voice-calibration", status_code=201)
async def voice_calibration(audio: UploadFile = File(...), user: dict = Depends(current_user), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict:
    calibration = {"id": serializers.new_id(), "user_id": user["id"], "embedding": [0.0] * 192, "sample_audio_url": f"local://{audio.filename}", "created_at": datetime.utcnow()}
    await db.voice_calibrations.insert_one(calibration)
    await db.users.update_one({"id": user["id"]}, {"$set": {"voice_calibration_id": calibration["id"]}})
    return {"calibration": serializers.clean(calibration)}


@router.post("/users/me/pi-pair", status_code=201)
async def pi_pair() -> dict:
    return {"pair_token": secrets.token_urlsafe(24), "expires_at": serializers.iso(datetime.utcnow() + timedelta(minutes=5))}


@router.post("/me/pair-device", status_code=201)
async def pair_device(payload: dict, user: dict = Depends(current_user), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict:
    token = payload.get("device_token") or payload.get("pi_qr_token") or secrets.token_urlsafe(24)
    device = {"id": serializers.new_id(), "auth_token": token, "owner_attendee_id": user.get("attendee_id"), "paired_at": datetime.utcnow(), "last_seen": datetime.utcnow()}
    await db.devices.update_one({"auth_token": token}, {"$set": device}, upsert=True)
    await db.users.update_one({"id": user["id"]}, {"$set": {"pi_paired_token": token}})
    return {"device": serializers.clean(device), "device_token": token}


@router.post("/pi/claim", status_code=201)
async def pi_claim(payload: dict, user: dict = Depends(current_user)) -> dict:
    return {"pi_token": f"pi_{payload.get('device_id', 'sim')}_{secrets.token_urlsafe(12)}", "user_id": user["id"]}


@router.post("/pairings", status_code=201)
async def create_pairing(user: dict = Depends(current_user), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict:
    token = secrets.token_urlsafe(16)
    expires = datetime.utcnow() + timedelta(seconds=60)
    await db.pairings.insert_one({"token": token, "issuer_user_id": user["id"], "expires_at": expires, "consumed_by_user_id": None, "consumed_at": None})
    return {"token": token, "expires_at": serializers.iso(expires), "qr_url": f"https://larpchekr.app/pair/{token}"}


@router.post("/pairings/consume", status_code=201)
async def consume_pairing(payload: dict, user: dict = Depends(current_user), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict:
    pairing = await db.pairings.find_one({"token": payload.get("token")})
    if pairing is None or pairing["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=404, detail={"error": {"code": "pairing_token_expired", "message": "pairing token invalid"}})
    event = await db.events.find_one()
    partner = await db.attendees.find_one({"email": user["email"]})
    session = {"id": serializers.new_id(), "event_id": event["id"], "wearer_id": pairing["issuer_user_id"], "self_user_id": pairing["issuer_user_id"], "subject_id": partner["id"] if partner else None, "partner_attendee_id": partner["id"] if partner else None, "partner_consent_status": "granted", "started_at": datetime.utcnow(), "ended_at": None, "device_id": "sim-pi", "pi_device_id": "sim-pi", "score": 0.0, "score_label": "mostly honest"}
    await db.sessions.insert_one(session)
    await db.pairings.update_one({"token": pairing["token"]}, {"$set": {"consumed_by_user_id": user["id"], "consumed_at": datetime.utcnow()}})
    return {"session_id": session["id"]}


@router.post("/sessions", status_code=201)
async def create_session(payload: dict, user: dict = Depends(current_user), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict:
    partner = await db.attendees.find_one({"event_id": payload["event_id"], "deleted_at": None})
    wearer_id = user.get("attendee_id") or user["id"]
    session = {"id": serializers.new_id(), "event_id": payload["event_id"], "wearer_id": wearer_id, "self_user_id": wearer_id, "subject_id": partner["id"] if partner else None, "partner_attendee_id": partner["id"] if partner else None, "partner_consent_status": "granted" if partner else "pending", "started_at": datetime.utcnow(), "ended_at": None, "device_id": payload.get("device_id", "sim-pi"), "pi_device_id": payload.get("device_id", "sim-pi"), "score": 0.0, "score_label": "mostly honest"}
    await db.sessions.insert_one(session)
    return {"session": serializers.session(session)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    session = await db.sessions.find_one({"id": session_id})
    if session is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "session_not_found", "message": "session not found"}})
    return {"session": serializers.session(session)}


@router.get("/me/sessions")
async def me_sessions(user: dict = Depends(current_user), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict:
    wearer_id = user.get("attendee_id") or user["id"]
    sessions = await db.sessions.find({"wearer_id": wearer_id}).sort("started_at", -1).to_list(50)
    if not sessions:
        sessions = await db.sessions.find({"self_user_id": wearer_id}).sort("started_at", -1).to_list(50)
    return {"sessions": [serializers.session(s) for s in sessions]}


@router.get("/sessions/{session_id}/recap")
async def recap(session_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    session = await db.sessions.find_one({"id": session_id})
    if session is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "session_not_found", "message": "session not found"}})
    utterances = await db.utterances.find({"session_id": session_id}).sort("started_at", 1).to_list(None)
    utterance_ids = [u["id"] for u in utterances]
    claims = await db.claims.find({"utterance_id": {"$in": utterance_ids}}).to_list(None)
    flags = await db.flags.find({"$or": [{"claim_id": {"$in": [c["id"] for c in claims]}}, {"session_id": session_id}]}).to_list(None)
    subject_id = session.get("subject_id") or session.get("partner_attendee_id")
    partner = await db.attendees.find_one({"id": subject_id}) if subject_id else None
    score = compute_score(flags)
    return {"session": serializers.session(session), "partner": serializers.attendee(partner) if partner else None, "subject": serializers.attendee(partner) if partner else None, "utterances": [serializers.utterance(u) for u in utterances], "claims": [serializers.claim(c) for c in claims], "flags": [serializers.flag(f) for f in flags], "score": score, "score_label": score_label(score)}


@router.post("/flags/{flag_id}/dispute")
async def dispute_flag(flag_id: str, payload: dict, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    await db.flags.update_one({"id": flag_id}, {"$set": {"disputed": True, "dispute_reason": payload.get("reason")}})
    await db.flags.update_one({"id": flag_id}, {"$set": {"dispute_status": "disputed"}})
    flag = await db.flags.find_one({"id": flag_id})
    if flag is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "flag not found"}})
    return {"flag": serializers.flag(flag)}


@router.post("/events", status_code=201)
async def create_event(payload: dict, user: dict = Depends(organizer_user), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=422, detail={"error": {"code": "invalid_event", "message": "event name is required"}})
    start_date = parse_dt(payload.get("start_date") or payload.get("starts_at") or datetime.utcnow().isoformat())
    end_date = parse_dt(payload.get("end_date") or payload.get("ends_at") or (datetime.utcnow() + timedelta(days=1)).isoformat())
    if end_date <= start_date:
        raise HTTPException(status_code=422, detail={"error": {"code": "invalid_event", "message": "event end date must be after start date"}})
    event = {"id": serializers.new_id(), "name": name, "start_date": start_date, "end_date": end_date, "starts_at": start_date, "ends_at": end_date, "organizer_ids": [user["id"]], "created_by_user_id": user["id"], "consent_jurisdiction": payload.get("consent_jurisdiction", "us-ca"), "retention_days": payload.get("retention_days", 30)}
    await db.events.insert_one(event)
    return {"event": serializers.event(event)}


@router.get("/events")
async def list_events(db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    events = await db.events.find().sort("start_date", 1).to_list(None)
    return {"events": [serializers.event(e) for e in events]}


@router.get("/events/{event_id}")
async def get_event(event_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    event = await require_event(db, event_id)
    count = await db.attendees.count_documents({"event_id": event_id, "deleted_at": None})
    return {"event": serializers.event(event, count)}


@router.post("/events/{event_id}/attendees/import", status_code=202)
async def import_attendees(event_id: str, csv_file: UploadFile = File(alias="csv"), db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(organizer_user)) -> dict:
    await require_event(db, event_id)
    try:
        rows = list(csv.DictReader(io.StringIO((await csv_file.read()).decode("utf-8-sig"))))
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail={"error": {"code": "invalid_csv", "message": "CSV must be UTF-8 encoded"}}) from exc
    errors = []
    attendees = []
    for index, row in enumerate(rows, start=2):
        firstname, lastname = split_name(row)
        if not firstname or not lastname:
            errors.append({"row_number": index, "row": row, "message": "missing firstname/lastname"})
            continue
        socials = social_links(row)
        embedding = [1.0] + [0.0] * 511
        profile_pic_url = row_value(row, "profile_pic_url", "photo_url") or None
        attendees.append({"id": serializers.new_id(), "event_id": event_id, "user_id": None, "firstname": firstname, "lastname": lastname, "full_name": f"{firstname} {lastname}", "email": row_value(row, "email"), "socials": socials, "headline": row_value(row, "headline") or None, "linkedin_url": socials["linkedin"], "github_login": socials["github"], "resume_url": row_value(row, "resume_url") or None, "profile_pic_url": profile_pic_url, "photo_url": profile_pic_url, "face_embedding": embedding, "verified_profile": {"languages": [{"name": "python", "evidence": "github", "confidence": 0.9, "loc": 12000}]}, "larp_score": None, "opt_in": {"public": True, "friends": True, "private": False}, "processing_status": "ready", "consented_to_recording": True, "imported_at": datetime.utcnow(), "deleted_at": None})
    if attendees:
        await db.attendees.insert_many(attendees)
    job = {"id": serializers.new_id(), "event_id": event_id, "status": "succeeded", "rows_total": len(rows), "rows_done": len(rows), "errors": errors}
    await db.import_jobs.insert_one(job)
    return {"import_job_id": job["id"], "estimated_seconds": 0}


@router.get("/events/{event_id}/attendees/import/{job_id}")
async def import_status(event_id: str, job_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    job = await db.import_jobs.find_one({"id": job_id, "event_id": event_id})
    if job is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "import_job_not_found", "message": "import job not found"}})
    return {"status": job["status"], "rows_total": job["rows_total"], "rows_done": job["rows_done"], "errors": job["errors"]}


@router.get("/events/{event_id}/attendees")
async def list_attendees(event_id: str, limit: int = 50, cursor: str | None = None, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    await require_event(db, event_id)
    limit = min(max(limit, 1), 200)
    rows = await db.attendees.find({"event_id": event_id, "deleted_at": None}).sort("full_name", 1).limit(limit).to_list(limit)
    attendee_ids = [row["id"] for row in rows]
    flags = await db.flags.find({"subject_id": {"$in": attendee_ids}}).to_list(None)
    flag_counts: dict[str, int] = {}
    for flag in flags:
        subject_id = flag.get("subject_id")
        if subject_id:
            flag_counts[subject_id] = flag_counts.get(subject_id, 0) + 1
    attendees = []
    for row in rows:
        attendee = serializers.attendee(row)
        attendee["flag_count"] = flag_counts.get(row["id"], 0)
        attendees.append(attendee)
    return {"attendees": attendees, "next_cursor": None}


@router.get("/events/{event_id}/leaderboard")
async def event_leaderboard(event_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    await require_event(db, event_id)
    return await build_leaderboard(db, event_id)


async def build_leaderboard(db: AsyncIOMotorDatabase, event_id: str | None = None) -> dict:
    query = {"deleted_at": None}
    if event_id:
        query["event_id"] = event_id
    rows = await db.attendees.find(query).to_list(None)
    attendee_ids = [row["id"] for row in rows]
    flags = await db.flags.find({"subject_id": {"$in": attendee_ids}}).to_list(None)
    flag_counts: dict[str, int] = {}
    for flag in flags:
        subject_id = flag.get("subject_id")
        if subject_id:
            flag_counts[subject_id] = flag_counts.get(subject_id, 0) + 1
    ranked = sorted(
        rows,
        key=lambda row: (row.get("larp_score") or 0, flag_counts.get(row["id"], 0), row.get("full_name") or ""),
        reverse=True,
    )
    return {
        "leaderboard": [
            {
                "rank": index + 1,
                "attendee": serializers.attendee(row),
                "larp_score": row.get("larp_score") or 0,
                "flag_count": flag_counts.get(row["id"], 0),
            }
            for index, row in enumerate(ranked)
        ]
    }


@router.get("/leaderboard")
async def global_leaderboard(event_id: str | None = None, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    if event_id:
        await require_event(db, event_id)
    return await build_leaderboard(db, event_id)


@router.get("/events/{event_id}/flags")
async def event_flags(event_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    await require_event(db, event_id)
    attendees = await db.attendees.find({"event_id": event_id, "deleted_at": None}).to_list(None)
    attendee_by_id = {attendee["id"]: attendee for attendee in attendees}
    flags = await db.flags.find({"subject_id": {"$in": list(attendee_by_id)}}).sort("created_at", -1).to_list(None)
    return {
        "flags": [
            {
                **serializers.flag(flag),
                "attendee": serializers.attendee(attendee_by_id[flag["subject_id"]]) if flag.get("subject_id") in attendee_by_id else None,
                "attendee_name": (attendee_by_id.get(flag.get("subject_id")) or {}).get("full_name"),
            }
            for flag in flags
        ]
    }


@router.get("/events/{event_id}/attendees/export")
async def export_attendees(event_id: str, token: str | None = None, db: AsyncIOMotorDatabase = Depends(get_db)) -> Response:
    return await export_event(event_id, token, db)


@router.get("/events/{event_id}/attendees/{attendee_id}")
async def attendee_detail(event_id: str, attendee_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    attendee = await db.attendees.find_one({"id": attendee_id, "event_id": event_id, "deleted_at": None})
    if attendee is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "attendee not found"}})
    flags = await db.flags.find({"subject_id": attendee_id}).sort("created_at", -1).to_list(100)
    return {"attendee": serializers.attendee(attendee), "flags": [serializers.flag(f) for f in flags]}


@router.post("/events/{event_id}/attendees", status_code=201)
async def create_attendee(event_id: str, payload: dict, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(organizer_user)) -> dict:
    await require_event(db, event_id)
    firstname, lastname = split_name(payload)
    if not firstname or not lastname:
        raise HTTPException(status_code=422, detail={"error": {"code": "invalid_attendee", "message": "firstname and lastname are required"}})
    attendee = {"id": serializers.new_id(), "event_id": event_id, "user_id": None, "firstname": firstname, "lastname": lastname, "full_name": f"{firstname} {lastname}", "email": payload.get("email", ""), "socials": payload.get("socials", {}), "headline": payload.get("headline"), "linkedin_url": payload.get("linkedin_url"), "github_login": payload.get("github_login"), "resume_url": payload.get("resume_url"), "photo_url": payload.get("photo_url"), "profile_pic_url": payload.get("profile_pic_url") or payload.get("photo_url"), "face_embedding": payload.get("face_embedding") or [1.0] + [0.0] * 511, "verified_profile": payload.get("verified_profile", {}), "larp_score": None, "processing_status": "ready", "opt_in": {"public": True, "friends": True, "private": False}, "consented_to_recording": payload.get("consented_to_recording", True), "imported_at": datetime.utcnow(), "deleted_at": None}
    await db.attendees.insert_one(attendee)
    return {"attendee": serializers.attendee(attendee)}


@router.patch("/events/{event_id}/attendees/{attendee_id}")
async def update_attendee(event_id: str, attendee_id: str, payload: dict, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(organizer_user)) -> dict:
    attendee = await db.attendees.find_one({"id": attendee_id, "event_id": event_id, "deleted_at": None})
    if attendee is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "attendee not found"}})
    update = {field: payload[field] for field in ["headline", "linkedin_url", "github_login", "resume_url", "full_name", "email", "firstname", "lastname", "socials", "profile_pic_url", "processing_status"] if field in payload}
    if not update:
        raise HTTPException(status_code=422, detail={"error": {"code": "invalid_attendee", "message": "no supported fields provided"}})
    if "firstname" in update or "lastname" in update:
        firstname = update.get("firstname") or attendee.get("firstname", "")
        lastname = update.get("lastname") or attendee.get("lastname", "")
        update["full_name"] = f"{firstname} {lastname}".strip()
    if "full_name" in update and ("firstname" not in update or "lastname" not in update):
        firstname, lastname = split_name({"full_name": update["full_name"]})
        if firstname and lastname:
            update.setdefault("firstname", firstname)
            update.setdefault("lastname", lastname)
    socials = dict(attendee.get("socials") or {})
    if "github_login" in update:
        socials["github"] = update["github_login"] or None
        update["socials"] = socials
    if "linkedin_url" in update:
        socials["linkedin"] = update["linkedin_url"] or None
        update["socials"] = socials
    await db.attendees.update_one({"id": attendee_id, "event_id": event_id}, {"$set": update})
    attendee = await db.attendees.find_one({"id": attendee_id})
    return {"attendee": serializers.attendee(attendee)}


@router.post("/events/{event_id}/attendees/{attendee_id}/profile-photo")
async def fetch_attendee_profile_photo(event_id: str, attendee_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(organizer_user)) -> dict:
    import httpx
    from app.identity.linkedin_scraper import scrape_linkedin_profile

    attendee = await db.attendees.find_one({"id": attendee_id, "event_id": event_id, "deleted_at": None})
    if attendee is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "attendee not found"}})

    image_url: str | None = None
    source = "unknown"

    # 1. Try LinkedIn via MCP scraper — photoUrl comes from og:image if the server exposes it
    linkedin_url = attendee.get("linkedin_url") or (attendee.get("socials") or {}).get("linkedin")
    if linkedin_url and linkedin_url.startswith("http"):
        li = await scrape_linkedin_profile(linkedin_url)
        if li.get("photoUrl"):
            image_url = li["photoUrl"]
            source = "linkedin_mcp"
            print(f"[PHOTO] got photoUrl from LinkedIn MCP: {image_url[:80]}")

    # 2. Fallback: GitHub avatar
    if not image_url:
        github_login = attendee.get("github_login") or (attendee.get("socials") or {}).get("github")
        if github_login:
            try:
                async with httpx.AsyncClient(timeout=6.0) as client:
                    resp = await client.get(
                        f"https://api.github.com/users/{github_login}",
                        headers={"Accept": "application/vnd.github+json"},
                    )
                    if resp.status_code == 200:
                        image_url = resp.json().get("avatar_url")
                        source = "github_avatar"
                        print(f"[PHOTO] using GitHub avatar: {image_url}")
            except Exception as exc:
                print(f"[PHOTO] GitHub avatar fetch failed: {exc}")

    if not image_url:
        raise HTTPException(status_code=404, detail={"error": {"code": "profile_photo_not_found", "message": "no profile photo could be resolved"}})

    await db.attendees.update_one(
        {"id": attendee_id, "event_id": event_id},
        {"$set": {"profile_pic_url": image_url, "photo_url": image_url, "profile_image_source": source, "processing_status": "ready"}},
    )
    attendee = await db.attendees.find_one({"id": attendee_id, "event_id": event_id})
    return {"attendee": serializers.attendee(attendee), "profile_pic_url": image_url, "source": source, "has_embedding": False}


@router.get("/events/{event_id}/attendees/{attendee_id}/summary")
async def attendee_summary(event_id: str, attendee_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    import httpx
    import json
    from dotenv import dotenv_values
    from pathlib import Path
    from app.identity.linkedin_scraper import scrape_linkedin_profile

    attendee = await db.attendees.find_one({"id": attendee_id, "event_id": event_id, "deleted_at": None})
    if attendee is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "attendee not found"}})

    print(f"\n{'='*60}")
    print(f"[SUMMARY] attendee={attendee.get('full_name')} id={attendee_id}")
    print(f"[SUMMARY] github_login={attendee.get('github_login')} linkedin_url={attendee.get('linkedin_url')}")
    print(f"{'='*60}\n")

    # ── GitHub ─────────────────────────────────────────────────────────────────
    github_data: dict = {}
    github_login = attendee.get("github_login") or (attendee.get("socials") or {}).get("github")
    if github_login:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                user_resp = await client.get(
                    f"https://api.github.com/users/{github_login}",
                    headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
                )
                print(f"[GITHUB] GET /users/{github_login} → {user_resp.status_code}")
                if user_resp.status_code == 200:
                    gh = user_resp.json()
                    github_data = {
                        "login": gh.get("login"),
                        "name": gh.get("name"),
                        "bio": gh.get("bio"),
                        "company": gh.get("company"),
                        "location": gh.get("location"),
                        "public_repos": gh.get("public_repos"),
                        "followers": gh.get("followers"),
                        "avatar_url": gh.get("avatar_url"),
                        "html_url": gh.get("html_url"),
                    }
                    print(f"[GITHUB] data={json.dumps({k:v for k,v in github_data.items() if k!='avatar_url'}, indent=2)}")

                repos_resp = await client.get(
                    f"https://api.github.com/users/{github_login}/repos",
                    params={"per_page": 100, "type": "owner", "sort": "pushed"},
                    headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
                )
                print(f"[GITHUB] GET /users/{github_login}/repos → {repos_resp.status_code}")
                if repos_resp.status_code == 200:
                    repos = repos_resp.json()
                    lang_counts: dict[str, int] = {}
                    for r in repos:
                        if r.get("language"):
                            lang_counts[r["language"]] = lang_counts.get(r["language"], 0) + 1
                    github_data["top_languages"] = sorted(lang_counts, key=lambda k: -lang_counts[k])[:6]
                    github_data["recent_repos"] = [
                        {"name": r["name"], "description": r.get("description"), "stars": r.get("stargazers_count", 0), "url": r.get("html_url")}
                        for r in repos[:5]
                    ]
                    print(f"[GITHUB] top_languages={github_data['top_languages']}")
                    print(f"[GITHUB] recent_repos={[r['name'] for r in github_data.get('recent_repos', [])]}")
        except Exception as exc:
            print(f"[GITHUB] ERROR: {exc}")

    # ── LinkedIn ───────────────────────────────────────────────────────────────
    linkedin_data: dict = {}
    linkedin_url = attendee.get("linkedin_url") or (attendee.get("socials") or {}).get("linkedin")
    print(f"[LINKEDIN] url={linkedin_url}")
    if linkedin_url and linkedin_url.startswith("http"):
        linkedin_data = await scrape_linkedin_profile(linkedin_url)
        # Full debug dump of everything we scraped
        print(f"[LINKEDIN] RAW RESULT:")
        try:
            safe = {k: v for k, v in linkedin_data.items() if k not in ("photoUrl",)}
            print(json.dumps(safe, indent=2, default=str))
        except Exception:
            print(repr(linkedin_data))
    else:
        print("[LINKEDIN] no URL — skipping scrape")

    # ── Flags & verified profile ───────────────────────────────────────────────
    flags = await db.flags.find({"subject_id": attendee_id}).sort("created_at", -1).to_list(50)
    profile = await db.profiles.find_one({"attendee_id": attendee_id})
    verified_profile = (profile.get("facts") if profile else None) or attendee.get("verified_profile") or {}
    print(f"[FLAGS] count={len(flags)}")
    print(f"[VERIFIED_PROFILE] keys={list(verified_profile.keys())}")

    # ── Claude comparison ──────────────────────────────────────────────────────
    comparison: dict = {}
    env_path = Path(__file__).resolve().parents[2] / ".env"
    anthropic_key = dotenv_values(env_path).get("ANTHROPIC_API_KEY") or settings.anthropic_api_key
    print(f"[CLAUDE] key_present={bool(anthropic_key)} linkedin_scraped={linkedin_data.get('scraped')} github_login={github_data.get('login')}")

    if anthropic_key and (linkedin_data.get("scraped") or github_data.get("login")):
        try:
            import anthropic
            client_ai = anthropic.Anthropic(api_key=anthropic_key)

            # Pass both the structured scrape and the full raw LinkedIn text so Claude
            # can compare the actual scraped profile data against GitHub evidence.
            raw_linkedin_text = linkedin_data.get("_raw_text", "") or ""
            linkedin_for_prompt = {k: v for k, v in linkedin_data.items() if k != "_raw_text"}

            gh_summary = ""
            if github_data.get("login"):
                gh_summary = f"""GitHub Profile:
- Login: {github_data.get('login')}
- Name: {github_data.get('name', 'N/A')}
- Bio: {github_data.get('bio', 'N/A')}
- Company: {github_data.get('company', 'N/A')}
- Public repos: {github_data.get('public_repos', 0)}
- Followers: {github_data.get('followers', 0)}
- Top languages: {', '.join(github_data.get('top_languages', []))}
- Recent repos: {json.dumps([r['name'] for r in github_data.get('recent_repos', [])])}"""
            else:
                gh_summary = "GitHub: not connected."

            attendee_name = attendee.get("full_name") or "this person"

            prompt = f"""You are analyzing the professional profile of {attendee_name} for a hackathon credential check system.

=== RAW LINKEDIN PAGE TEXT ===
{raw_linkedin_text[:4000] if raw_linkedin_text else "(LinkedIn not available)"}

=== STRUCTURED LINKEDIN DATA ===
{json.dumps(linkedin_for_prompt, indent=2, default=str)[:6000]}

=== GITHUB DATA ===
{gh_summary}

Tasks — respond ONLY with a single JSON object, no markdown fences:
1. "extracted": Extract structured data from the LinkedIn text into:
   - "experiences": list of {{title, company, dates}} — look for job titles, org names, date ranges anywhere in the text
   - "education": list of {{school, degree}}
   - "skills": list of skill names mentioned anywhere (programming languages, tools, frameworks, soft skills)
2. "linkedin_summary": 2-3 sentence summary of their LinkedIn background and claims.
3. "github_summary": 1-2 sentence summary of what GitHub activity actually shows.
4. "discrepancies": array of specific mismatches between LinkedIn claims and GitHub evidence.
5. "credibility": one of CONSISTENT / MINOR_GAPS / SIGNIFICANT_GAPS
6. "credibility_reason": 1-sentence reason.
7. "larp_score": number from 0.0 to 1.0 where 0 means the profiles match and 1 means major professional claims look unsupported.
8. "larp_score_reason": 1 sentence explaining that score."""

            print(f"[CLAUDE] calling claude-haiku-4-5 for extraction + comparison...")
            resp = client_ai.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_resp = resp.content[0].text.strip()
            print(f"[CLAUDE] raw response:\n{raw_resp}")

            json_match = re.search(r'\{.*\}', raw_resp, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                comparison = {k: v for k, v in parsed.items() if k != "extracted"}

                # Merge Claude-extracted structured data back into linkedin_data
                extracted = parsed.get("extracted") or {}
                if extracted.get("experiences"):
                    linkedin_data["experiences"] = extracted["experiences"]
                if extracted.get("education"):
                    linkedin_data["education"] = extracted["education"]
                if extracted.get("skills"):
                    linkedin_data["skills"] = extracted["skills"]

                print(f"[CLAUDE] credibility={comparison.get('credibility')} extracted_exp={len(linkedin_data.get('experiences', []))} skills={linkedin_data.get('skills', [])[:5]}")
            else:
                comparison = {"linkedin_summary": raw_resp, "github_summary": "", "discrepancies": [], "credibility": "UNKNOWN", "credibility_reason": ""}

        except Exception as exc:
            print(f"[CLAUDE] ERROR: {exc}")
            comparison = {"error": str(exc)}

    from app.pipeline.score import calculate_profile_larp_score
    
    ai_score = comparison.get("larp_score")
    if isinstance(ai_score, int | float):
        profile_score = max(0.0, min(1.0, float(ai_score)))
        profile_label = score_label(profile_score)
    else:
        profile_score, profile_label = calculate_profile_larp_score(comparison)
    
    # Update the field the dashboard list and summary actually render.
    await db.attendees.update_one(
        {"id": attendee_id},
        {"$set": {"larp_score": profile_score, "profile_larp_score": profile_score}}
    )
    attendee = await db.attendees.find_one({"id": attendee_id, "event_id": event_id}) or attendee
    
    print(f"\n[SUMMARY DONE] github_keys={list(github_data.keys())} linkedin_scraped={linkedin_data.get('scraped')} comparison_keys={list(comparison.keys())} profile_larp_score={profile_score}\n")

    return {
        "attendee": serializers.attendee(attendee),
        "github": github_data,
        "linkedin": linkedin_data,
        "comparison": comparison,
        "verified_profile": verified_profile,
        "flags": [serializers.flag(f) for f in flags],
        "larp_score": profile_score,
        "profile_larp_score": profile_score,
        "profile_larp_label": profile_label,
    }


@router.delete("/events/{event_id}/attendees/{attendee_id}")
async def delete_attendee(event_id: str, attendee_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(organizer_user)) -> dict:
    attendee = await db.attendees.find_one({"id": attendee_id, "event_id": event_id, "deleted_at": None})
    if attendee is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "attendee not found"}})
    await db.attendees.update_one({"id": attendee_id, "event_id": event_id}, {"$set": {"deleted_at": datetime.utcnow()}})
    attendee = await db.attendees.find_one({"id": attendee_id})
    return {"attendee": serializers.attendee(attendee)}


@router.get("/events/{event_id}/export")
async def export_event(event_id: str, token: str | None = None, db: AsyncIOMotorDatabase = Depends(get_db)) -> Response:
    await user_from_export_token(db, token)
    await require_event(db, event_id)
    rows = await db.attendees.find({"event_id": event_id, "deleted_at": None}).sort("full_name", 1).to_list(None)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=["firstname", "lastname", "email", "headline", "linkedin", "github", "instagram", "website", "larp_score", "processing_status", "profile_pic_url"])
    writer.writeheader()
    for a in rows:
        socials = a.get("socials") or {}
        writer.writerow({"firstname": a.get("firstname"), "lastname": a.get("lastname"), "email": a.get("email"), "headline": a.get("headline"), "linkedin": socials.get("linkedin") or a.get("linkedin_url"), "github": socials.get("github") or a.get("github_login"), "instagram": socials.get("instagram"), "website": socials.get("website"), "larp_score": a.get("larp_score"), "processing_status": a.get("processing_status"), "profile_pic_url": a.get("profile_pic_url")})
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{event_id}-attendees.csv"'})


@router.get("/events/{event_id}/stats")
async def event_stats(event_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    await require_event(db, event_id)
    attendee_count = await db.attendees.count_documents({"event_id": event_id, "deleted_at": None})
    registered = await db.attendees.count_documents({"event_id": event_id, "user_id": {"$ne": None}, "deleted_at": None})
    attendee_ids = [a["id"] for a in await db.attendees.find({"event_id": event_id, "deleted_at": None}).to_list(None)]
    flags = await db.flags.find({"subject_id": {"$in": attendee_ids}}).sort("created_at", -1).to_list(None)
    scored = [a for a in await db.attendees.find({"event_id": event_id, "larp_score": {"$ne": None}, "deleted_at": None}).to_list(None)]
    avg_score = sum(a.get("larp_score", 0) for a in scored) / len(scored) if scored else 0
    return {"attendees": attendee_count, "avg_score": avg_score, "flags": len(flags), "registered": registered, "latest_flag": serializers.flag(flags[0]) if flags else None}

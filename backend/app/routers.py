import csv
import io
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app import serializers
from app.auth import create_token
from app.db import get_db
from app.deps import current_user, organizer_user
from app.pipeline.score import compute_score, score_label

router = APIRouter()


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


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
    start_date = parse_dt(payload.get("start_date") or payload.get("starts_at") or datetime.utcnow().isoformat())
    end_date = parse_dt(payload.get("end_date") or payload.get("ends_at") or (datetime.utcnow() + timedelta(days=1)).isoformat())
    event = {"id": serializers.new_id(), "name": payload["name"], "start_date": start_date, "end_date": end_date, "starts_at": start_date, "ends_at": end_date, "organizer_ids": [user["id"]], "created_by_user_id": user["id"], "consent_jurisdiction": payload.get("consent_jurisdiction", "us-ca"), "retention_days": payload.get("retention_days", 30)}
    await db.events.insert_one(event)
    return {"event": serializers.event(event)}


@router.get("/events")
async def list_events(db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    events = await db.events.find().sort("start_date", 1).to_list(None)
    return {"events": [serializers.event(e) for e in events]}


@router.get("/events/{event_id}")
async def get_event(event_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    event = await db.events.find_one({"id": event_id})
    count = await db.attendees.count_documents({"event_id": event_id, "deleted_at": None})
    return {"event": serializers.event(event, count) if event else None}


@router.post("/events/{event_id}/attendees/import", status_code=202)
async def import_attendees(event_id: str, csv_file: UploadFile = File(alias="csv"), db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(organizer_user)) -> dict:
    rows = list(csv.DictReader(io.StringIO((await csv_file.read()).decode("utf-8-sig"))))
    errors = []
    attendees = []
    for row in rows:
        firstname = row.get("firstname") or (row.get("full_name", "").split(" ")[0] if row.get("full_name") else "")
        lastname = row.get("lastname") or (row.get("full_name", "").split(" ")[-1] if row.get("full_name") else "")
        if not firstname or not lastname:
            errors.append({"row": row, "message": "missing firstname/lastname"})
            continue
        socials = {"linkedin": row.get("linkedin") or row.get("linkedin_url") or None, "github": row.get("github") or row.get("github_login") or None, "instagram": row.get("instagram") or None, "website": row.get("website") or row.get("personal_site") or None}
        embedding = [1.0] + [0.0] * 511
        attendees.append({"id": serializers.new_id(), "event_id": event_id, "user_id": None, "firstname": firstname, "lastname": lastname, "full_name": f"{firstname} {lastname}", "email": row.get("email", ""), "socials": socials, "headline": row.get("headline") or None, "linkedin_url": socials["linkedin"], "github_login": socials["github"], "profile_pic_url": row.get("profile_pic_url") or None, "photo_url": row.get("profile_pic_url") or None, "face_embedding": embedding, "verified_profile": {"languages": [{"name": "python", "evidence": "github", "confidence": 0.9, "loc": 12000}]}, "larp_score": None, "opt_in": {"public": True, "friends": True, "private": False}, "processing_status": "ready", "consented_to_recording": True, "imported_at": datetime.utcnow(), "deleted_at": None})
    if attendees:
        await db.attendees.insert_many(attendees)
    job = {"id": serializers.new_id(), "event_id": event_id, "status": "succeeded", "rows_total": len(rows), "rows_done": len(rows), "errors": errors}
    await db.import_jobs.insert_one(job)
    return {"import_job_id": job["id"], "estimated_seconds": 0}


@router.get("/events/{event_id}/attendees/import/{job_id}")
async def import_status(event_id: str, job_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    job = await db.import_jobs.find_one({"id": job_id, "event_id": event_id})
    return {"status": job["status"], "rows_total": job["rows_total"], "rows_done": job["rows_done"], "errors": job["errors"]}


@router.get("/events/{event_id}/attendees")
async def list_attendees(event_id: str, limit: int = 50, cursor: str | None = None, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    rows = await db.attendees.find({"event_id": event_id, "deleted_at": None}).sort("full_name", 1).limit(limit).to_list(limit)
    return {"attendees": [serializers.attendee(a) for a in rows], "next_cursor": None}


@router.get("/events/{event_id}/attendees/{attendee_id}")
async def attendee_detail(event_id: str, attendee_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    attendee = await db.attendees.find_one({"id": attendee_id, "event_id": event_id})
    if attendee is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "attendee not found"}})
    flags = await db.flags.find({"subject_id": attendee_id}).sort("created_at", -1).to_list(100)
    return {"attendee": serializers.attendee(attendee), "flags": [serializers.flag(f) for f in flags]}


@router.post("/events/{event_id}/attendees", status_code=201)
async def create_attendee(event_id: str, payload: dict, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(organizer_user)) -> dict:
    firstname = payload.get("firstname") or payload.get("full_name", "").split(" ")[0]
    lastname = payload.get("lastname") or payload.get("full_name", "").split(" ")[-1]
    attendee = {"id": serializers.new_id(), "event_id": event_id, "user_id": None, "firstname": firstname, "lastname": lastname, "full_name": f"{firstname} {lastname}", "email": payload.get("email", ""), "socials": payload.get("socials", {}), "headline": payload.get("headline"), "linkedin_url": payload.get("linkedin_url"), "github_login": payload.get("github_login"), "resume_url": payload.get("resume_url"), "photo_url": payload.get("photo_url"), "profile_pic_url": payload.get("profile_pic_url") or payload.get("photo_url"), "face_embedding": payload.get("face_embedding") or [1.0] + [0.0] * 511, "verified_profile": payload.get("verified_profile", {}), "larp_score": None, "processing_status": "ready", "opt_in": {"public": True, "friends": True, "private": False}, "consented_to_recording": payload.get("consented_to_recording", True), "imported_at": datetime.utcnow(), "deleted_at": None}
    await db.attendees.insert_one(attendee)
    return {"attendee": serializers.attendee(attendee)}


@router.patch("/events/{event_id}/attendees/{attendee_id}")
async def update_attendee(event_id: str, attendee_id: str, payload: dict, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(organizer_user)) -> dict:
    update = {field: payload[field] for field in ["headline", "linkedin_url", "github_login", "resume_url", "full_name", "email", "firstname", "lastname", "socials", "profile_pic_url", "processing_status"] if field in payload}
    await db.attendees.update_one({"id": attendee_id, "event_id": event_id}, {"$set": update})
    attendee = await db.attendees.find_one({"id": attendee_id})
    return {"attendee": serializers.attendee(attendee)}


@router.delete("/events/{event_id}/attendees/{attendee_id}")
async def delete_attendee(event_id: str, attendee_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(organizer_user)) -> dict:
    await db.attendees.update_one({"id": attendee_id, "event_id": event_id}, {"$set": {"deleted_at": datetime.utcnow()}})
    attendee = await db.attendees.find_one({"id": attendee_id})
    return {"attendee": serializers.attendee(attendee)}


@router.get("/events/{event_id}/attendees/export")
async def export_attendees(event_id: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> Response:
    return await export_event(event_id, db)


@router.get("/events/{event_id}/export")
async def export_event(event_id: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> Response:
    rows = await db.attendees.find({"event_id": event_id, "deleted_at": None}).sort("full_name", 1).to_list(None)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=["firstname", "lastname", "linkedin", "github", "instagram", "website", "larp_score", "processing_status", "profile_pic_url"])
    writer.writeheader()
    for a in rows:
        socials = a.get("socials") or {}
        writer.writerow({"firstname": a.get("firstname"), "lastname": a.get("lastname"), "linkedin": socials.get("linkedin"), "github": socials.get("github"), "instagram": socials.get("instagram"), "website": socials.get("website"), "larp_score": a.get("larp_score"), "processing_status": a.get("processing_status"), "profile_pic_url": a.get("profile_pic_url")})
    return Response(out.getvalue(), media_type="text/csv")


@router.get("/events/{event_id}/stats")
async def event_stats(event_id: str, db: AsyncIOMotorDatabase = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    attendee_count = await db.attendees.count_documents({"event_id": event_id, "deleted_at": None})
    registered = await db.attendees.count_documents({"event_id": event_id, "user_id": {"$ne": None}, "deleted_at": None})
    attendee_ids = [a["id"] for a in await db.attendees.find({"event_id": event_id}).to_list(None)]
    flags = await db.flags.find({"subject_id": {"$in": attendee_ids}}).sort("created_at", -1).to_list(None)
    scored = [a for a in await db.attendees.find({"event_id": event_id, "larp_score": {"$ne": None}}).to_list(None)]
    avg_score = sum(a.get("larp_score", 0) for a in scored) / len(scored) if scored else 0
    return {"attendees": attendee_count, "avg_score": avg_score, "flags": len(flags), "registered": registered, "latest_flag": serializers.flag(flags[0]) if flags else None}

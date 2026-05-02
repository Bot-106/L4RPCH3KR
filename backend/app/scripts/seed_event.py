import asyncio
from datetime import datetime, timedelta

from app import serializers
from app.auth import create_token
from app.db import database


async def main() -> None:
    db = database()
    organizer = await db.users.find_one({"email": "organizer@example.com"})
    if organizer is None:
        organizer = {"id": serializers.new_id(), "email": "organizer@example.com", "display_name": "Organizer", "role": "organizer", "created_at": datetime.utcnow(), "attendee_id": None, "github_login": None, "pi_paired_token": None}
        await db.users.insert_one(organizer)

    event = await db.events.find_one({"name": "L4RPCH3KR Demo Hackathon"})
    if event is None:
        start = datetime.utcnow()
        end = start + timedelta(days=2)
        event = {"id": serializers.new_id(), "name": "L4RPCH3KR Demo Hackathon", "start_date": start, "end_date": end, "starts_at": start, "ends_at": end, "organizer_ids": [organizer["id"]], "created_by_user_id": organizer["id"], "consent_jurisdiction": "us-ca", "retention_days": 30}
        await db.events.insert_one(event)

    wearer_attendee = await db.attendees.find_one({"event_id": event["id"], "email": "wearer@example.com"})
    if wearer_attendee is None:
        wearer_attendee = {"id": serializers.new_id(), "event_id": event["id"], "user_id": None, "firstname": "Wendy", "lastname": "Wearer", "full_name": "Wendy Wearer", "email": "wearer@example.com", "socials": {}, "verified_profile": {}, "profile_pic_url": None, "photo_url": None, "face_embedding": [0.0, 1.0] + [0.0] * 510, "larp_score": None, "opt_in": {"public": True, "friends": True, "private": False}, "processing_status": "ready", "consented_to_recording": True, "imported_at": datetime.utcnow(), "deleted_at": None}
        await db.attendees.insert_one(wearer_attendee)

    wearer = await db.users.find_one({"email": "wearer@example.com"})
    if wearer is None:
        wearer = {"id": serializers.new_id(), "email": "wearer@example.com", "display_name": "Wearer", "role": "attendee", "created_at": datetime.utcnow(), "attendee_id": wearer_attendee["id"], "github_login": None, "pi_paired_token": "dev-pi"}
        await db.users.insert_one(wearer)
    await db.attendees.update_one({"id": wearer_attendee["id"]}, {"$set": {"user_id": wearer["id"]}})

    subject = await db.attendees.find_one({"event_id": event["id"], "email": "partner@example.com"})
    if subject is None:
        subject = {"id": serializers.new_id(), "event_id": event["id"], "user_id": None, "firstname": "Pat", "lastname": "Python", "full_name": "Pat Python", "email": "partner@example.com", "socials": {"linkedin": "https://linkedin.com/in/patpython", "github": "patpython", "instagram": None, "website": "https://patpython.dev"}, "headline": "Python backend engineer", "linkedin_url": "https://linkedin.com/in/patpython", "github_login": "patpython", "verified_profile": {"languages": [{"name": "python", "evidence": "github", "confidence": 0.9, "loc": 12000}], "experience": [], "education": [], "projects": [], "credentials": []}, "profile_pic_url": "https://avatars.githubusercontent.com/u/1", "photo_url": "https://avatars.githubusercontent.com/u/1", "face_embedding": [1.0] + [0.0] * 511, "larp_score": None, "opt_in": {"public": True, "friends": True, "private": False}, "processing_status": "ready", "consented_to_recording": True, "imported_at": datetime.utcnow(), "deleted_at": None}
        await db.attendees.insert_one(subject)
    await db.attendees.update_many({"event_id": event["id"], "id": {"$ne": subject["id"]}}, {"$set": {"face_embedding": [0.0, 1.0] + [0.0] * 510}})
    await db.attendees.update_one({"id": subject["id"]}, {"$set": {"face_embedding": [1.0] + [0.0] * 511, "processing_status": "ready", "verified_profile": {"languages": [{"name": "python", "evidence": "github", "confidence": 0.9, "loc": 12000}], "experience": [], "education": [], "projects": [], "credentials": []}}})

    if await db.profiles.find_one({"attendee_id": subject["id"]}) is None:
        await db.profiles.insert_one({"id": serializers.new_id(), "attendee_id": subject["id"], "source": "github", "fetched_at": datetime.utcnow(), "data": {"login": "patpython"}, "facts": subject["verified_profile"]})

    await db.devices.update_one({"auth_token": "dev-pi"}, {"$set": {"id": "dev-pi", "auth_token": "dev-pi", "owner_attendee_id": wearer_attendee["id"], "paired_at": datetime.utcnow(), "last_seen": datetime.utcnow()}}, upsert=True)

    session = await db.sessions.find_one({"event_id": event["id"], "wearer_id": wearer_attendee["id"]})
    if session is None:
        session = {"id": serializers.new_id(), "event_id": event["id"], "wearer_id": wearer_attendee["id"], "self_user_id": wearer_attendee["id"], "subject_id": subject["id"], "partner_attendee_id": subject["id"], "device_id": "dev-pi", "pi_device_id": "dev-pi", "partner_consent_status": "granted", "started_at": datetime.utcnow(), "ended_at": None, "score": 0.0, "score_label": "mostly honest"}
        await db.sessions.insert_one(session)

    print(f"event_id={event['id']}")
    print(f"subject_id={subject['id']}")
    print(f"session_id={session['id']}")
    print(f"device_token=dev-pi")
    print(f"organizer_jwt={create_token(organizer['id'], 'organizer')}")
    print(f"wearer_jwt={create_token(wearer['id'], 'attendee')}")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio

from app.db import database


async def main() -> None:
    db = database()
    await db.users.create_index("email", unique=True)
    await db.events.create_index("start_date")
    await db.attendees.create_index([("event_id", 1), ("lastname", 1)])
    await db.attendees.create_index([("event_id", 1), ("firstname", 1)])
    await db.attendees.create_index([("event_id", 1), ("email", 1)])
    await db.sessions.create_index([("wearer_id", 1), ("started_at", -1)])
    await db.sessions.create_index("subject_id")
    await db.utterances.create_index([("session_id", 1), ("started_at", 1)])
    await db.claims.create_index("utterance_id")
    await db.flags.create_index([("subject_id", 1), ("created_at", -1)])
    await db.flags.create_index("session_id")
    await db.flags.create_index("claim_id")
    await db.devices.create_index("auth_token", unique=True)
    await db.profiles.create_index("attendee_id")
    await db.import_jobs.create_index([("event_id", 1), ("id", 1)])
    print("Mongo indexes ready")


if __name__ == "__main__":
    asyncio.run(main())

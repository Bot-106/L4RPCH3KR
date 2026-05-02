from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app import serializers
from app.auth import create_token
from app.routers import (
    create_event,
    delete_attendee,
    event_stats,
    export_event,
    get_event,
    import_attendees,
    import_status,
    list_attendees,
    update_attendee,
)


def matches(doc: dict, query: dict) -> bool:
    for key, expected in query.items():
        if key == "$or":
            if not any(matches(doc, branch) for branch in expected):
                return False
            continue
        actual = doc.get(key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$ne" in expected and actual == expected["$ne"]:
                return False
        elif actual != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def sort(self, key: str, direction: int):
        self.rows.sort(key=lambda row: row.get(key) or "", reverse=direction < 0)
        return self

    def limit(self, limit: int):
        self.rows = self.rows[:limit]
        return self

    async def to_list(self, limit: int | None):
        return self.rows if limit is None else self.rows[:limit]


class FakeCollection:
    def __init__(self, rows: list[dict] | None = None):
        self.rows = rows or []

    async def find_one(self, query: dict | None = None, *args, **kwargs):
        query = query or {}
        rows = [row for row in self.rows if matches(row, query)]
        for key, direction in kwargs.get("sort") or []:
            rows.sort(key=lambda row: row.get(key) or "", reverse=direction < 0)
        return rows[0] if rows else None

    async def insert_one(self, doc: dict):
        self.rows.append(doc)

    async def insert_many(self, docs: list[dict]):
        self.rows.extend(docs)

    def find(self, query: dict | None = None):
        query = query or {}
        return FakeCursor([row for row in self.rows if matches(row, query)])

    async def update_one(self, query: dict, update: dict):
        row = await self.find_one(query)
        if row and "$set" in update:
            row.update(update["$set"])

    async def count_documents(self, query: dict):
        return len([row for row in self.rows if matches(row, query)])


class FakeDb:
    def __init__(self, user: dict):
        self.users = FakeCollection([user])
        self.events = FakeCollection()
        self.attendees = FakeCollection()
        self.import_jobs = FakeCollection()
        self.flags = FakeCollection()


class FakeUpload:
    filename = "attendees.csv"

    def __init__(self, text: str):
        self.data = text.encode("utf-8")

    async def read(self) -> bytes:
        return self.data


@pytest.mark.asyncio
async def test_dashboard_event_attendee_import_update_delete_export_flow() -> None:
    user = {"id": serializers.new_id(), "email": "organizer@example.com", "display_name": "Organizer", "role": "organizer", "created_at": datetime.utcnow()}
    db = FakeDb(user)

    created = await create_event(
        {
            "name": "Functional Demo",
            "starts_at": datetime.utcnow().isoformat(),
            "ends_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        },
        user,
        db,
    )
    event_id = created["event"]["id"]
    loaded = await get_event(event_id, db, user)
    assert loaded["event"]["name"] == "Functional Demo"
    assert loaded["event"]["attendee_count"] == 0

    csv_text = "full_name,email,github,linkedin,headline\nPat Python,pat@example.com,patpython,https://linkedin.test/pat,Backend engineer\nSingle,single@example.com,single,,Missing last name\nAda Lovelace,ada@example.com,adalove,,Math hacker\n"
    job = await import_attendees(event_id, FakeUpload(csv_text), db, user)
    status = await import_status(event_id, job["import_job_id"], db, user)
    assert status["status"] == "succeeded"
    assert status["rows_total"] == 3
    assert len(status["errors"]) == 1

    attendees = await list_attendees(event_id, 50, None, db, user)
    assert [attendee["full_name"] for attendee in attendees["attendees"]] == ["Ada Lovelace", "Pat Python"]

    pat = next(attendee for attendee in attendees["attendees"] if attendee["full_name"] == "Pat Python")
    updated = await update_attendee(event_id, pat["id"], {"full_name": "Pat Updated", "github_login": "updatedhub"}, db, user)
    assert updated["attendee"]["firstname"] == "Pat"
    assert updated["attendee"]["lastname"] == "Updated"
    assert updated["attendee"]["socials"]["github"] == "updatedhub"

    ada = next(attendee for attendee in attendees["attendees"] if attendee["full_name"] == "Ada Lovelace")
    deleted = await delete_attendee(event_id, ada["id"], db, user)
    assert deleted["attendee"]["deleted_at"] is not None
    after_delete = await list_attendees(event_id, 50, None, db, user)
    assert [attendee["full_name"] for attendee in after_delete["attendees"]] == ["Pat Updated"]

    next(row for row in db.attendees.rows if row["id"] == pat["id"])["larp_score"] = 0.5
    db.flags.rows.append({"id": serializers.new_id(), "subject_id": pat["id"], "session_id": serializers.new_id(), "severity": "medium", "created_at": datetime.utcnow()})
    stats = await event_stats(event_id, db, user)
    assert stats["attendees"] == 1
    assert stats["avg_score"] == 0.5
    assert stats["flags"] == 1
    assert stats["latest_flag"]["severity"] == "medium"

    response = await export_event(event_id, create_token(user["id"], "organizer"), db)
    body = response.body.decode()
    assert "firstname,lastname,email,headline,linkedin,github,instagram,website,larp_score,processing_status,profile_pic_url" in body
    assert "Pat,Updated" in body
    assert "Ada,Lovelace" not in body


@pytest.mark.asyncio
async def test_dashboard_routes_return_404_for_missing_records() -> None:
    user = {"id": serializers.new_id(), "email": "organizer@example.com", "display_name": "Organizer", "role": "organizer", "created_at": datetime.utcnow()}
    db = FakeDb(user)

    with pytest.raises(HTTPException) as event_exc:
        await get_event("missing-event", db, user)
    assert event_exc.value.status_code == 404

    with pytest.raises(HTTPException) as job_exc:
        await import_status("missing-event", "missing-job", db, user)
    assert job_exc.value.status_code == 404

    created = await create_event(
        {
            "name": "Functional Demo",
            "starts_at": datetime.utcnow().isoformat(),
            "ends_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        },
        user,
        db,
    )
    event_id = created["event"]["id"]

    with pytest.raises(HTTPException) as update_exc:
        await update_attendee(event_id, "missing-attendee", {"headline": "Nope"}, db, user)
    assert update_exc.value.status_code == 404

    with pytest.raises(HTTPException) as delete_exc:
        await delete_attendee(event_id, "missing-attendee", db, user)
    assert delete_exc.value.status_code == 404

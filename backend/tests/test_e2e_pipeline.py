from datetime import datetime

import pytest

from app import serializers
from app.pipeline.fixtures import LARP_TEXT, TRUTHFUL_TEXT
from app.pipeline.orchestrator import process_simulated_utterance
from app.routers import recap
from app.ws_manager import manager


def matches(doc: dict, query: dict) -> bool:
    for key, expected in query.items():
        if key == "$or":
            if not any(matches(doc, branch) for branch in expected):
                return False
            continue
        actual = doc.get(key)
        if isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
        elif actual != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def sort(self, key: str, direction: int):
        self.rows.sort(key=lambda row: row.get(key), reverse=direction < 0)
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
        return next((row for row in self.rows if matches(row, query)), None)

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

    async def create_index(self, *args, **kwargs):
        return None


class FakeDb:
    def __init__(self):
        event_id = serializers.new_id()
        user_id = serializers.new_id()
        partner_id = serializers.new_id()
        session_id = serializers.new_id()
        self.session_id = session_id
        self.users = FakeCollection([{"id": user_id, "email": "wearer@example.com", "display_name": "Wearer", "role": "attendee", "created_at": datetime.utcnow()}])
        self.events = FakeCollection([{"id": event_id, "name": "Demo", "start_date": datetime.utcnow(), "end_date": datetime.utcnow(), "organizer_ids": [user_id], "starts_at": datetime.utcnow(), "ends_at": datetime.utcnow(), "consent_jurisdiction": "us-ca", "retention_days": 30, "created_by_user_id": user_id}])
        self.attendees = FakeCollection([{"id": partner_id, "event_id": event_id, "firstname": "Pat", "lastname": "Python", "full_name": "Pat Python", "email": "partner@example.com", "socials": {"github": "patpython"}, "verified_profile": {"languages": [{"name": "python", "evidence": "github", "confidence": 0.9, "loc": 12000}]}, "consented_to_recording": True, "processing_status": "ready", "imported_at": datetime.utcnow(), "deleted_at": None}])
        self.profiles = FakeCollection([{"id": serializers.new_id(), "attendee_id": partner_id, "source": "github", "fetched_at": datetime.utcnow(), "data": {}, "facts": {"languages": [{"name": "python", "evidence": "github", "confidence": 0.9, "loc": 12000}]}}])
        self.sessions = FakeCollection([{"id": session_id, "event_id": event_id, "wearer_id": user_id, "subject_id": partner_id, "self_user_id": user_id, "partner_attendee_id": partner_id, "partner_consent_status": "granted", "started_at": datetime.utcnow(), "ended_at": None, "device_id": "sim-pi", "pi_device_id": "sim-pi"}])
        self.utterances = FakeCollection()
        self.claims = FakeCollection()
        self.flags = FakeCollection()
        self.import_jobs = FakeCollection()
        self.voice_calibrations = FakeCollection()
        self.pairings = FakeCollection()


@pytest.mark.asyncio
async def test_two_known_claims_emit_exactly_one_flag_and_recap(monkeypatch) -> None:
    db = FakeDb()
    phone_events: list[tuple[str, dict]] = []
    haptics: list[str] = []

    async def fake_send_phone(session_id: str, event_type: str, data: dict) -> None:
        phone_events.append((event_type, data))

    async def fake_send_pi_haptic(severity: str) -> None:
        haptics.append(severity)

    monkeypatch.setattr(manager, "send_phone", fake_send_phone)
    monkeypatch.setattr(manager, "send_pi_haptic", fake_send_pi_haptic)

    await process_simulated_utterance(db, db.session_id, TRUTHFUL_TEXT)
    await process_simulated_utterance(db, db.session_id, LARP_TEXT)

    flags = [event for event in phone_events if event[0] == "flag_raised"]
    assert len(flags) == 1
    assert haptics == ["medium"]

    data = await recap(db.session_id, db, {"id": "fixture-user"})
    assert len(data["utterances"]) == 2
    assert len(data["claims"]) == 2
    assert len(data["flags"]) == 1
    assert data["flags"][0]["verified_text"].startswith("GitHub/profile facts show no Rust")

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


@pytest.mark.asyncio
async def test_absurd_live_claims_and_buzzwords_are_flagged_and_scored(monkeypatch) -> None:
    db = FakeDb()
    phone_events: list[tuple[str, dict]] = []
    haptics: list[str] = []

    async def fake_send_phone(session_id: str, event_type: str, data: dict) -> None:
        phone_events.append((event_type, data))

    async def fake_send_pi_haptic(severity: str) -> None:
        haptics.append(severity)

    async def fake_extract_claims(text: str, utterance_id: str) -> list[dict]:
        return [
            {
                "id": serializers.new_id(),
                "utterance_id": utterance_id,
                "text": text,
                "kind": "quantitative",
                "claim_type": "quantitative",
                "subject": "people",
                "predicate": "rounded_up",
                "value": {"metric": "people", "amount": 50_000_000_000, "unit": "count"},
                "hedge": "strong",
                "extraction_confidence": 0.3,
                "confidence": 0.3,
                "text_span": "I rounded up 50 billion people",
            },
            {
                "id": serializers.new_id(),
                "utterance_id": utterance_id,
                "text": text,
                "kind": "buzzword",
                "claim_type": "buzzword",
                "subject": "agentic",
                "predicate": "startup_buzzword",
                "value": {"keyword": "agentic"},
                "hedge": "none",
                "extraction_confidence": 0.9,
                "confidence": 0.9,
                "text_span": "agentic b2b saas",
            },
        ]

    monkeypatch.setattr(manager, "send_phone", fake_send_phone)
    monkeypatch.setattr(manager, "send_pi_haptic", fake_send_pi_haptic)
    monkeypatch.setattr("app.pipeline.orchestrator.extract_claims", fake_extract_claims)

    await process_simulated_utterance(db, db.session_id, "I rounded up 50 billion people with an agentic b2b saas.", speaker="subject")

    flags = [event for event in phone_events if event[0] == "flag_raised"]
    assert len(flags) == 2
    assert {flag[1]["flag"]["severity"] for flag in flags} == {"high", "medium"}
    assert haptics == ["high", "medium"]
    session = await db.sessions.find_one({"id": db.session_id})
    attendee = await db.attendees.find_one({"id": db.attendees.rows[0]["id"]})
    assert session["score"] > 0
    assert attendee["larp_score"] > 0


@pytest.mark.asyncio
async def test_misheard_b2b_saas_and_5000_companies_are_flagged(monkeypatch) -> None:
    db = FakeDb()
    phone_events: list[tuple[str, dict]] = []

    async def fake_send_phone(session_id: str, event_type: str, data: dict) -> None:
        phone_events.append((event_type, data))

    async def fake_send_pi_haptic(severity: str) -> None:
        return None

    async def fake_extract_claims(text: str, utterance_id: str) -> list[dict]:
        return [
            {
                "id": serializers.new_id(),
                "utterance_id": utterance_id,
                "text": text,
                "kind": "employment",
                "claim_type": "employment",
                "subject": "multiple companies",
                "predicate": "interning_at",
                "value": {"company": "5,000 different companies", "title": "intern"},
                "hedge": "strong",
                "extraction_confidence": 0.3,
                "confidence": 0.3,
                "text_span": "I am interning at 5,000 different companies",
            },
            {
                "id": serializers.new_id(),
                "utterance_id": utterance_id,
                "text": text,
                "kind": "employment",
                "claim_type": "employment",
                "subject": "5000 V2B AI SAC",
                "predicate": "interned_at",
                "value": {"company": "5000 V2B AI SAC", "title": "Intern"},
                "hedge": "none",
                "extraction_confidence": 0.85,
                "confidence": 0.85,
                "text_span": "interned at 5000 V2B AI SAC",
            },
        ]

    monkeypatch.setattr(manager, "send_phone", fake_send_phone)
    monkeypatch.setattr(manager, "send_pi_haptic", fake_send_pi_haptic)
    monkeypatch.setattr("app.pipeline.orchestrator.extract_claims", fake_extract_claims)

    await process_simulated_utterance(db, db.session_id, "Hello, I interned at 5000 V2B AI SAC and 5,000 different companies.", speaker="subject")

    flags = [event for event in phone_events if event[0] == "flag_raised"]
    assert len(flags) == 2
    assert all(flag[1]["flag"]["severity"] == "high" for flag in flags)

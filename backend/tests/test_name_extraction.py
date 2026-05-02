from datetime import datetime

import pytest

from app.identity.name_extraction import extract_spoken_name, resolve_by_name


class FakeCursor:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    async def to_list(self, limit: int | None):
        return self.rows if limit is None else self.rows[:limit]


class FakeCollection:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def find(self, query: dict | None = None):
        query = query or {}
        return FakeCursor([row for row in self.rows if all(row.get(k) == v for k, v in query.items())])


class FakeDb:
    def __init__(self):
        self.attendees = FakeCollection([
            {"id": "arnnav", "event_id": "event", "firstname": "Arnnav", "lastname": "Kudale", "imported_at": datetime.utcnow()},
            {"id": "other", "event_id": "event", "firstname": "Wenya", "lastname": "Wang", "imported_at": datetime.utcnow()},
        ])


def test_extract_spoken_name_is_case_insensitive() -> None:
    assert extract_spoken_name("we have my name is Arno") == ("Arno", None)


@pytest.mark.asyncio
async def test_resolve_by_name_accepts_asr_variants_for_arnnav() -> None:
    db = FakeDb()
    assert await resolve_by_name(db, "event", "my name is Arno") == "arnnav"
    assert await resolve_by_name(db, "event", "I'm Arnav") == "arnnav"
    assert await resolve_by_name(db, "event", "I am Arnov") == "arnnav"

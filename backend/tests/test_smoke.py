import pytest
from fastapi import HTTPException

from app.deps import current_user
from app.main import app
from app.pipeline.extract import extract_claim


class EmptyUsers:
    async def find_one(self, *args, **kwargs):
        return None


class EmptyDb:
    users = EmptyUsers()


def test_app_imports() -> None:
    assert app.title == "L4RPCH3KR API"


@pytest.mark.asyncio
async def test_keyword_claim_extraction() -> None:
    claim = await extract_claim("I have shipped production Rust for five years.", "01HX0000000000000000000000")
    assert claim is not None
    assert claim["subject"] == "rust"


@pytest.mark.asyncio
async def test_invalid_bearer_token_returns_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await current_user("Bearer invalid-token", EmptyDb())

    assert exc.value.status_code == 401

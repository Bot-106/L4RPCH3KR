import pytest

from app.main import app
from app.pipeline.extract import extract_claim


def test_app_imports() -> None:
    assert app.title == "L4RPCH3KR API"


@pytest.mark.asyncio
async def test_keyword_claim_extraction() -> None:
    claim = await extract_claim("I have shipped production Rust for five years.", "01HX0000000000000000000000")
    assert claim is not None
    assert claim["subject"] == "rust"

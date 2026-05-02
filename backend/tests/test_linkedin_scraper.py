from app.identity.linkedin_scraper import _normalize, _parse_profile_text


def test_parse_profile_text_extracts_core_sections() -> None:
    parsed = _parse_profile_text(
        """
Pat Python
Backend Engineer | Python | FastAPI
San Francisco, California, United States
1,234 followers
About
I build APIs and data pipelines.
Experience
Senior Engineer
Acme Corp
2022 - Present
Education
Example University
BS Computer Science
Skills
Python
FastAPI
"""
    )

    assert parsed["name"] == "Pat Python"
    assert parsed["headline"] == "Backend Engineer | Python | FastAPI"
    assert parsed["location"] == "San Francisco, California, United States"
    assert parsed["followers"] == "1,234 followers"
    assert parsed["about"] == "I build APIs and data pipelines."
    assert parsed["experiences"] == [
        {"title": "Senior Engineer", "company": "Acme Corp", "dates": "2022 - Present"}
    ]
    assert parsed["education"] == [
        {"school": "Example University", "degree": "BS Computer Science"}
    ]
    assert parsed["skills"] == ["Python", "FastAPI"]


def test_normalize_mcp_profile_keeps_raw_text_for_haiku() -> None:
    normalized = _normalize(
        {"sections": {"main_profile": "Pat Python\nBackend Engineer | Python"}},
        "https://www.linkedin.com/in/patpython",
    )

    assert normalized["scraped"] is True
    assert normalized["name"] == "Pat Python"
    assert normalized["headline"] == "Backend Engineer | Python"
    assert normalized["_raw_text"] == "Pat Python\nBackend Engineer | Python"

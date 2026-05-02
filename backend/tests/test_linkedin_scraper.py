from app.identity.linkedin_scraper import linkedin_user_id_from_url, normalize_linkedin_profile


def test_linkedin_user_id_from_url() -> None:
    assert linkedin_user_id_from_url("https://www.linkedin.com/in/patpython") == "patpython"
    assert linkedin_user_id_from_url("https://linkedin.com/in/pat-python_1/") == "pat-python_1"
    assert linkedin_user_id_from_url("linkedin.com/in/pat.python") == "pat.python"
    assert linkedin_user_id_from_url("https://www.linkedin.com/company/example") is None


def test_normalize_linkedin_profile() -> None:
    normalized = normalize_linkedin_profile(
        {
            "Basic Details": {
                "Name": "Pat Python",
                "Title": "Backend Engineer",
                "Summary": "Builds APIs",
            },
            "Work Experience Details": [{"Title": "Engineer", "Company": "Acme"}],
            "Education Details": [{"Institute": "Example University"}],
            "Project Details": [{"Name": "Verifier"}],
            "Recommendations": ["Great teammate"],
        },
        "https://www.linkedin.com/in/patpython",
    )

    assert normalized["name"] == "Pat Python"
    assert normalized["headline"] == "Backend Engineer"
    assert normalized["about"] == "Builds APIs"
    assert normalized["experiences"] == [{"Title": "Engineer", "Company": "Acme"}]
    assert normalized["education"] == [{"Institute": "Example University"}]
    assert normalized["projects"] == [{"Name": "Verifier"}]
    assert normalized["recommendations"] == ["Great teammate"]
    assert normalized["scraped"] is True

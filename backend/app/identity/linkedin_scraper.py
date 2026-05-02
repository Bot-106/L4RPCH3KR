"""LinkedIn profile scraper via linkedin-mcp-server.

Calls the MCP server running on port 9000 directly over HTTP using raw
JSON-RPC — no mcp client library needed, so there are no dependency conflicts.

Start the server once with:
  uvx linkedin-scraper-mcp@latest --transport streamable-http --port 9000
"""

import json
import logging
import re
from typing import Any

import httpx

log = logging.getLogger(__name__)

MCP_URL = "http://localhost:9000/mcp"
_MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


async def _mcp_call(client: httpx.AsyncClient, method: str, params: dict, req_id: int = 1, session_id: str | None = None) -> Any:
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params,
    }
    headers = {**_MCP_HEADERS, **({"Mcp-Session-Id": session_id} if session_id else {})}
    resp = await client.post(MCP_URL, json=payload, headers=headers, timeout=60.0)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        result_text = None
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                result_text = line[5:].strip()
        if not result_text:
            raise ValueError("empty SSE stream from MCP server")
        envelope = json.loads(result_text)
    else:
        envelope = resp.json()

    if "error" in envelope:
        raise RuntimeError(f"MCP error: {envelope['error']}")
    return envelope.get("result")


async def scrape_linkedin_profile(url: str) -> dict[str, Any]:
    if not url or not url.startswith("http"):
        return {}

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            # 1. Initialize — capture session ID
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "larpchekr", "version": "1.0"},
                },
            }
            init_resp = await client.post(MCP_URL, json=init_payload, headers=_MCP_HEADERS, timeout=30.0)
            init_resp.raise_for_status()
            session_id = init_resp.headers.get("mcp-session-id") or init_resp.headers.get("Mcp-Session-Id")
            log.info("linkedin_mcp: initialized session_id=%s", session_id)

            # 2. notifications/initialized
            notif_headers = {**_MCP_HEADERS, **({"Mcp-Session-Id": session_id} if session_id else {})}
            await client.post(MCP_URL, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=notif_headers, timeout=10.0)

            # 3. Call the tool with just the username
            username = url.rstrip("/").split("/")[-1]
            log.info("linkedin_mcp: get_person_profile username=%s", username)
            result = await _mcp_call(client, "tools/call", {
                "name": "get_person_profile",
                "arguments": {"linkedin_username": username},
            }, req_id=2, session_id=session_id)

        log.info("linkedin_mcp: got result type=%s", type(result))
        print(f"[LINKEDIN MCP] raw result:\n{json.dumps(result, indent=2, default=str)}")

        if isinstance(result, dict) and "content" in result:
            blocks = result["content"]
            raw_text = next((b["text"] for b in blocks if b.get("type") == "text"), None)
        elif isinstance(result, str):
            raw_text = result
        else:
            raw_text = json.dumps(result)

        try:
            data = json.loads(raw_text)
        except (json.JSONDecodeError, TypeError):
            data = {"raw_text": raw_text}

        return _normalize(data, url)

    except Exception as exc:
        log.warning("linkedin_mcp: failed for %s: %s", url, exc)
        print(f"[LINKEDIN MCP] ERROR: {exc}")
        return {"scraped": False, "error": str(exc)}


def _parse_profile_text(text: str) -> dict[str, Any]:
    """Parse the raw main_profile text blob returned by linkedin-mcp-server."""
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l]

    result: dict[str, Any] = {}

    # Name is always the first line
    if lines:
        result["name"] = lines[0]

    # Headline: look for a line with " | " or job-related keywords
    SKIP = {"he/him", "she/her", "they/them", "add verification badge", "open to", "add section",
            "enhance profile", "resources", "analytics", "private to you", "show all",
            "contact info", "500+ connections", "1st", "2nd", "3rd"}
    for line in lines[1:10]:
        if line.lower() in SKIP:
            continue
        if " | " in line or any(kw in line.lower() for kw in [
            "developer", "engineer", "student", "founder", "captain", "manager",
            "building", "designer", "researcher", "director", "lead", "head of"
        ]):
            result["headline"] = line
            break

    # Location: "City, Province, Country" pattern
    for line in lines[1:15]:
        if re.match(r'^[A-Z][^|·\n]{2,},[^|·\n]{2,}', line) and len(line) < 60:
            result["location"] = line
            break

    # Followers
    for line in lines:
        m = re.search(r'([\d,]+)\s+followers', line, re.IGNORECASE)
        if m:
            result["followers"] = m.group(0)
            break

    # About section
    about_idx = next((i for i, l in enumerate(lines) if l.lower() == "about"), None)
    if about_idx is not None:
        about_parts = []
        for l in lines[about_idx + 1: about_idx + 10]:
            if l.lower() in ("featured", "activity", "experience", "education", "skills", "show all", "… more"):
                break
            about_parts.append(l)
        if about_parts:
            result["about"] = " ".join(about_parts)

    # Experience section
    exp_idx = next((i for i, l in enumerate(lines) if l.lower() == "experience"), None)
    if exp_idx is not None:
        experiences = []
        i = exp_idx + 1
        while i < len(lines) and lines[i].lower() not in ("education", "skills", "show all", "activity", "featured"):
            title = lines[i]
            company = lines[i + 1] if i + 1 < len(lines) else ""
            has_dates = i + 2 < len(lines) and re.search(r'\d{4}|present|mo\b|yr\b', lines[i + 2], re.I)
            dates = lines[i + 2] if has_dates else ""
            if title and not title.lower().startswith("show"):
                experiences.append({"title": title, "company": company, "dates": dates})
            i += 3 if dates else 2
            if len(experiences) >= 8:
                break
        result["experiences"] = experiences

    # Education section
    edu_idx = next((i for i, l in enumerate(lines) if l.lower() == "education"), None)
    if edu_idx is not None:
        education = []
        i = edu_idx + 1
        while i < len(lines) and lines[i].lower() not in ("skills", "show all", "experience", "activity", "featured"):
            school = lines[i]
            degree = lines[i + 1] if i + 1 < len(lines) and lines[i + 1].lower() not in ("skills", "show all") else ""
            if school and not school.lower().startswith("show"):
                education.append({"school": school, "degree": degree})
            i += 2
            if len(education) >= 6:
                break
        result["education"] = education

    # Skills section
    skills_idx = next((i for i, l in enumerate(lines) if l.lower() == "skills"), None)
    if skills_idx is not None:
        skills = []
        for l in lines[skills_idx + 1: skills_idx + 30]:
            if l.lower() in ("show all", "endorsements", "add skills", "show all skills"):
                break
            if len(l) < 60 and not l.startswith("·") and not l.isdigit():
                skills.append(l)
        result["skills"] = skills[:20]

    return result


def _normalize(raw: dict[str, Any], url: str) -> dict[str, Any]:
    if not raw:
        return {"scraped": False}

    # linkedin-mcp-server v1 format: {url, sections: {main_profile: "text"}, references}
    sections = raw.get("sections") or {}
    main_text = sections.get("main_profile") or ""

    if main_text:
        parsed = _parse_profile_text(main_text)
        print(f"[LINKEDIN PARSED] {json.dumps({k: v for k, v in parsed.items() if k != 'about'}, indent=2, default=str)}")
        return {
            "scraped": bool(parsed.get("name")),
            "url": url,
            "name": parsed.get("name"),
            "headline": parsed.get("headline"),
            "about": parsed.get("about"),
            "location": parsed.get("location"),
            "followers": parsed.get("followers"),
            "photoUrl": None,
            "experiences": parsed.get("experiences", []),
            "education": parsed.get("education", []),
            "skills": parsed.get("skills", []),
            # Pass full raw text so Claude can extract what regex missed
            "_raw_text": main_text,
        }

    # Fallback: flat keys from older server versions
    def pick(*keys: str) -> Any:
        for k in keys:
            v = raw.get(k)
            if v not in (None, "", [], {}):
                return v
        return None

    return {
        "scraped": True,
        "url": url,
        "name": pick("name", "fullName", "full_name"),
        "headline": pick("headline", "title", "occupation"),
        "about": pick("about", "summary", "description"),
        "location": pick("location", "geoLocation", "geo_location"),
        "followers": pick("followers", "followersCount", "followers_count"),
        "photoUrl": pick("photoUrl", "photo_url", "profilePicture"),
        "experiences": [],
        "education": [],
        "skills": [],
    }

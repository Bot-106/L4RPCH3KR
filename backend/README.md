# backend/ - Server

FastAPI backend for L4RPCH3KR, built for the EurekaHacks 2026 demo. It owns auth, event data, attendee data, Pi/phone websockets, transcript ingestion, claim extraction, profile comparison, flag creation, and larp scoring.

## Scope

- REST API for organizers, attendees, events, imports, exports, profiles, flags, and the Larperboard.
- Pi websocket endpoint for session events, transcript/frame payloads, haptic responses, and disconnect-safe cleanup.
- Phone websocket endpoint for live flag and score updates.
- MongoDB persistence for events, attendees, sessions, utterances, claims, flags, profile summaries, and scores.
- LLM-backed claim extraction and profile comparison.
- GitHub profile lookup plus LinkedIn/profile-context comparison support.
- CSV import/export for organizer workflows.
- Smoke tests for health, auth behavior, event flows, and core API paths.

## Tech Stack

- Python 3.11
- FastAPI + Uvicorn
- MongoDB
- Anthropic/OpenAI-compatible LLM calls for structured claim/profile analysis
- PyGithub/httpx for external profile data
- pytest + pytest-asyncio for tests

## Local Environment

Copy `.env.example` to `.env` and configure the required values.

| Var | Purpose |
|-----|---------|
| `MONGO_URL` | MongoDB connection string |
| `MONGO_DB` | Database name |
| `JWT_SECRET` | JWT signing secret |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | LLM provider credentials |
| `LLM_MODEL` | Model used for extraction/comparison |
| `GITHUB_TOKEN` | Optional GitHub API token |
| `LINKEDIN_COOKIE` | Optional LinkedIn/MCP scraper credential |

## Running Locally

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API server: `http://localhost:8000`

Tailscale URL from other devices: `http://100.76.124.67:8000`

If other Tailscale devices cannot reach the backend, allow inbound TCP `8000` in Windows Firewall. The server must bind to `0.0.0.0`; binding to the default `127.0.0.1` only works on this PC.

Health check: `GET /healthz`

## Testing

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest
```

## Main Interfaces

- `GET /healthz`
- `POST /auth/*`
- `GET /events`
- `POST /events`
- `GET /events/{event_id}/attendees`
- `POST /events/{event_id}/attendees`
- `POST /events/{event_id}/import`
- `GET /events/{event_id}/export`
- `GET /events/{event_id}/flags`
- `GET /events/{event_id}/leaderboard`
- `GET /leaderboard`
- `WS /ws/pi`
- `WS /ws/phone`

See [`../contracts/`](../contracts/README.md) for shared REST/websocket/data contracts.

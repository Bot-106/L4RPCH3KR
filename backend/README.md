# backend/ — Server

Owner: **Engineer B**.

The brain. Everything that's not a UI or a piece of hardware lives here. Same engineer also owns [`dashboard/`](../dashboard/README.md).

## Scope

In:
- HTTP REST API (see `contracts/rest-api.md`).
- Two WS endpoints (`/ws/pi`, `/ws/phone`) per `contracts/websocket-events.md`.
- ASR pipeline (faster-whisper).
- Speaker diarization via ECAPA-TDNN embedding match.
- Claim extraction (LLM, structured output).
- Profile fetching + caching (GitHub, LinkedIn-via-CSV, resume parse).
- Comparison engine (claim ↔ profile facts → flag or no flag).
- Larp scoring.
- Async background workers (CSV import enrichment, profile refresh, transcript finalize).
- Magic-link email + GitHub OAuth.
- Postgres migrations.
- WS pub/sub via Redis for multi-process scale (one process is fine for v1).

Out (v1):
- Multi-region.
- A separate ML serving tier (we run faster-whisper in-process; if that's too slow we'll containerize it).
- Streaming partial transcripts (we wait for utterance-end).
- Anti-abuse / rate limiting beyond per-user 60 rpm.

## Tech stack

- **Python 3.11**
- **FastAPI** + **uvicorn** (`--workers 1` for v1, `--reload` in dev)
- **Postgres 15** with `pgvector` for voice embeddings
- **Redis 7** for WS pub/sub and short-lived state
- **SQLAlchemy 2.0** + **Alembic** for ORM/migrations
- **faster-whisper** (CTranslate2) for ASR — `small.en` default, configurable
- **speechbrain** ECAPA-TDNN for speaker embeddings
- **Anthropic Python SDK** for claim extraction (or OpenAI; configurable per env)
- **PyGithub** for GitHub profile fetch
- **httpx** for any other outbound HTTP
- **arq** for background workers (Redis-backed)
- **pytest** + **pytest-asyncio** for tests
- **ruff** for lint

## File layout

```
backend/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── alembic.ini
├── alembic/
│   └── versions/              ← migrations (Engineer B)
├── app/
│   ├── __init__.py
│   ├── main.py                ← FastAPI app factory
│   ├── config.py              ← pydantic settings
│   ├── db.py                  ← SQLAlchemy engine + session
│   ├── redis.py               ← redis client
│   ├── deps.py                ← FastAPI dependencies (auth, db session)
│   ├── auth/
│   │   ├── jwt.py
│   │   ├── magic_link.py
│   │   └── github_oauth.py
│   ├── models/                ← SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── event.py
│   │   ├── attendee.py
│   │   ├── session.py
│   │   ├── utterance.py
│   │   ├── claim.py
│   │   ├── flag.py
│   │   ├── profile.py
│   │   └── voice_calibration.py
│   ├── routers/               ← FastAPI route modules
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── pairings.py
│   │   ├── sessions.py
│   │   ├── flags.py
│   │   └── organizer.py       ← /events/* endpoints
│   ├── ws/
│   │   ├── pi.py              ← /ws/pi handler
│   │   ├── phone.py           ← /ws/phone handler
│   │   └── pubsub.py          ← redis fan-out
│   ├── pipeline/
│   │   ├── asr.py             ← faster-whisper wrapper
│   │   ├── diarize.py         ← ECAPA embedding match
│   │   ├── extract.py         ← LLM claim extraction
│   │   ├── compare.py         ← claim ↔ profile-facts → flag
│   │   ├── score.py           ← larp score
│   │   └── orchestrator.py    ← drives audio → flag for one session
│   ├── profiles/
│   │   ├── github.py
│   │   ├── linkedin.py        ← parses CSV-supplied LinkedIn URLs (no scraping in v1)
│   │   └── resume.py          ← PDF text extract + LLM normalize
│   ├── workers/
│   │   ├── enrich_csv.py
│   │   └── refresh_profile.py
│   ├── contracts/
│   │   └── generated/         ← from /contracts (gitignored)
│   └── scripts/
│       ├── sim_pi.py          ← simulates a Pi for end-to-end dev
│       └── seed_event.py      ← creates a fake Event + Attendees for demo
└── tests/
    ├── test_routers/
    ├── test_pipeline/
    └── conftest.py
```

## External interfaces

### Consumes
- Postgres + Redis (local docker-compose, prod managed).
- Anthropic / OpenAI API for claim extraction.
- GitHub API (PAT or OAuth on behalf of user).
- SMTP (resend.com or postmark for magic-link delivery).
- Audio binary frames + JSON WS from Pi clients.
- JSON WS from phone clients.

### Exposes
- REST API on `:8000` per `contracts/rest-api.md`.
- WS endpoints on `:8000/ws/pi`, `:8000/ws/phone` per `contracts/websocket-events.md`.

### Local environment
Reads from `backend/.env`:

| Var | Required | Example |
|-----|----------|---------|
| `DATABASE_URL` | yes | `postgresql+asyncpg://localhost:5432/larpchekr` |
| `REDIS_URL` | yes | `redis://localhost:6379/0` |
| `JWT_SECRET` | yes | random 64 bytes |
| `MAGIC_LINK_FROM` | yes | `noreply@larpchekr.app` |
| `RESEND_API_KEY` | yes (prod) | |
| `GITHUB_OAUTH_CLIENT_ID` / `GITHUB_OAUTH_CLIENT_SECRET` | yes | |
| `LLM_PROVIDER` | yes | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | one of, depending on provider | |
| `LLM_MODEL` | yes | `claude-sonnet-4-6` or `gpt-4.1-mini` |
| `WHISPER_MODEL` | yes | `small.en` |
| `STORAGE_BACKEND` | yes | `local` (dev) or `s3` |
| `S3_BUCKET` / `S3_REGION` | s3 only | |

## Local setup

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# infra
docker compose -f ../infra/docker-compose.dev.yml up -d postgres redis

# migrations + seed
alembic upgrade head
python -m app.scripts.seed_event

# server
uvicorn app.main:app --reload

# in another shell, simulate a pi:
python -m app.scripts.sim_pi --session-id <id-from-seed>
```

## MVP checklist

- [ ] Postgres schema for all models, migrations land cleanly.
- [ ] `/healthz` green.
- [ ] Magic-link auth issues a JWT.
- [ ] GitHub OAuth links `github_login` to a user.
- [ ] `POST /users/me/voice-calibration` stores an embedding.
- [ ] `POST /pairings` + `POST /pairings/consume` create a Session.
- [ ] `POST /pi/claim` issues a Pi token.
- [ ] WS `/ws/pi` accepts `pi_hello`, audio frames, frame snapshots.
- [ ] WS `/ws/phone` accepts `subscribe_session`, fans out events.
- [ ] Pipeline: audio → ASR → diarize → utterance row written.
- [ ] Pipeline: partner utterance → claim extraction → claim row.
- [ ] Pipeline: claim → compare(profile facts) → flag row + WS `flag_raised` + WS `haptic_pulse`.
- [ ] Larp score recomputed on each new flag, emitted via `score_update`.
- [ ] `GET /sessions/:id/recap` returns a complete recap.
- [ ] CSV import endpoint runs through `app.workers.enrich_csv`.
- [ ] Latency p50 utterance-end → flag emit ≤ 4s on a laptop. (Profile per-stage and document.)

## Non-goals

- A separate model-serving microservice. (Will containerize ASR if it's the bottleneck.)
- Per-flag voting / community moderation.
- Push notifications.
- Anything that requires a paid LinkedIn API tier.

## Open questions

- **LLM provider:** Claude Sonnet 4.6 or gpt-4.1-mini? Decide on day 0 based on credit. Keep the interface in `app/pipeline/extract.py` provider-agnostic so we can flip.
- **Whisper model size:** `small.en` is fast but slightly lossy on hedges. Test `medium.en` if GPU available; fall back to `small.en` on CPU-only deploy.
- **Diarization fallback:** if ECAPA misclassifies >20% of utterances in user testing, do we add a second mic on the Pi? Track this in week 1 testing — if true, the Pi needs a hardware change (out of v1).
- **Flag persistence vs. session-end finalize:** are flags durable as soon as written, or do we let the user redact pre-recap? Default: durable, with `disputed` for soft-redaction.
- **Profile refresh cadence:** GitHub profile changes between import and conversation. Refresh on first session use, max once per 24h, surface staleness in the flag's `verified_text`.

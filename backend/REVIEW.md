# Backend Review

## Issues found

### [FIXED] Category: CORS hardcoded origins

**File:** `backend/app/main.py` (lines 46-55 before fix), `backend/app/config.py`

**What was wrong:** `main.py` had three hardcoded CORS origins (`http://localhost:3000`, `http://localhost:8000`, `http://100.90.235.28:3000`) that could not be overridden without editing source code. The Tailscale IP `100.90.235.28` was stale and neither the web-phone nor the dashboard host.

**What was changed:**
- Added `cors_origins: str` field to `Settings` in `config.py` with default `"http://100.76.124.67:3000,http://100.76.124.67:3001"`.
- Added `cors_origins_list()` helper method on `Settings` that splits the comma-separated value and strips whitespace.
- Updated `main.py` to call `settings.cors_origins_list()` instead of the hardcoded list.
- The `CORS_ORIGINS` env var is now documented in `backend/.env.example`.


### [FIXED] Category: Missing `.env.example`

**File:** `backend/.env.example` (created)

**What was wrong:** The file was referenced in `backend/README.md` setup instructions (`cp .env.example .env`) but did not exist.

**What was changed:** Created `backend/.env.example` with all env vars from `config.py` plus those listed in `backend/README.md` (`MAGIC_LINK_FROM`, `RESEND_API_KEY`, `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, `STORAGE_BACKEND`). Each var has an inline comment. The new vars were also added to `config.py` with sensible defaults so the app does not crash if they are absent.


### [FIXED] Category: WS auth uses path param, contracts require query param

**File:** `backend/app/main.py`

**What was wrong:** Two path-param routes existed:
- `@app.websocket("/ws/phone/{user_token}")` — path param `user_token`
- `@app.websocket("/ws/pi/{device_token}")` — path param `device_token`

Contracts (`contracts/websocket-events.md`) specify auth via `?token=<token>` query param.

**What was changed:**
- Removed the `/{user_token}` and `/{device_token}` path-param route variants entirely.
- Added `token: str | None = Query(default=None)` parameter to `phone_ws()` and `pi_ws()` route functions.
- Renamed handler signatures from `device_token`/`user_token` to `token` for consistency.
- Updated `backend/app/scripts/verify_e2e.py` WS connection strings from `/ws/phone/dev` and `/ws/pi/dev-pi` to `/ws/phone?token=dev` and `/ws/pi?token=dev-pi`.


### [FIXED] Category: `sim_pi.py` default URL uses path-param auth and wrong host

**File:** `backend/app/scripts/sim_pi.py` line 19

**What was wrong:** Default `--url` was `ws://localhost:8000/ws/pi/dev-pi` — used path-param auth (now removed) and localhost instead of the Tailscale backend IP.

**What was changed:** Default changed to `ws://100.76.124.67:8000/ws/pi?token=dev-token`.


### [FIXED] Category: `verify_e2e.py` default base-url uses localhost

**File:** `backend/app/scripts/verify_e2e.py` line 46

**What was wrong:** Default `--base-url` was `http://127.0.0.1:8000`.

**What was changed:** Default changed to `http://100.76.124.67:8000`.


### [FIXED] Category: WS event name drift — `subject_identified` vs `partner_identified`

**File:** `backend/app/main.py` (frame_snapshot handler)

**What was wrong:** All three `manager.send_phone(session_id, "subject_identified", ...)` calls emitted the event name `subject_identified`. Contracts (`contracts/websocket-events.md`, Backend → phone table) specify `partner_identified`.

**What was changed:** All three occurrences renamed to `partner_identified`. The intermediate variable was also renamed from `payload` to `pi_payload` to avoid shadowing the outer `payload` variable.


### [FIXED] Category: `/debug/config` leaks config state without auth

**File:** `backend/app/main.py` lines 35-43 (before fix)

**What was wrong:** `GET /debug/config` was publicly accessible with no auth, returning whether API keys are configured. This leaks operational state to anyone who can reach the backend.

**What was changed:** The endpoint now returns HTTP 404 unless `settings.fixture_mode` is `True`. In production (`FIXTURE_MODE=false`) it is unreachable. A docstring explaining this policy was added to the function.


### [FIXED] Category: Structured logging missing at WS handler boundaries

**File:** `backend/app/main.py`

**What was wrong:** No structured logging at the websocket handler entry points. Difficult to trace session/event activity in logs.

**What was changed:** Added `log.info(...)` calls at:
- WS connect time for `/ws/phone` and `/ws/pi` (logs `endpoint`, `token_present`, `request_id`).
- Each JSON message received in both handlers (logs `endpoint`, `event_type`, `session_id`, `request_id`).

Each entry is a JSON-formatted string for easy parsing. Binary audio frames are not logged per-frame (would be too noisy). A `request_id` (8-char UUID prefix) is generated per WS connection and threaded through all log entries for that connection.

An `import uuid` was added to `main.py`.


### [FIXED] Category: Pre-existing test failures

**Files:** `backend/tests/test_smoke.py`, `backend/app/pipeline/compare.py`

**What was wrong (two separate issues):**

1. `test_smoke.py::test_keyword_claim_extraction` called `extract_claim(...)` synchronously (no `await`), but `extract_claim` is an `async` function. This caused `TypeError: 'coroutine' object is not subscriptable` at runtime.

2. `test_e2e_pipeline.py::test_two_known_claims_emit_exactly_one_flag_and_recap` asserted `data["flags"][0]["verified_text"].startswith("GitHub/profile facts show no Rust")`, but `compare.py` produced `"No evidence of rust found in verified GitHub profile (known: python)."`.

**What was changed:**
- `test_smoke.py`: Added `import pytest`, changed `test_keyword_claim_extraction` to `async def` with `@pytest.mark.asyncio`, and added `await` to the `extract_claim(...)` call.
- `compare.py`: Updated the `verified_text` format string for `language_experience` mismatches to start with `"GitHub/profile facts show no {subject.capitalize()} in verified profile ..."`, matching the test contract.


### [FLAGGED] Category: MongoDB URL default is localhost

**File:** `backend/app/config.py` line 8

**Disposition: intentional — no change needed.**

`mongo_url` defaults to `mongodb://localhost:27017`. Per the deployment topology, MongoDB runs on the same host as the FastAPI backend (`100.76.124.67`). localhost is correct for this configuration. Documented in `.env.example`.


---

## Out of scope — orchestrator decision needed

### `subject_resolved` backend→Pi event not in contracts

`backend/app/main.py` emits `subject_resolved` back to the Pi after each `frame_snapshot`. This event does not appear in `contracts/websocket-events.md` (Backend → Pi table). It was not removed because it is live functionality the Pi may depend on. The orchestrator should either:
- Add it to the contracts as an official event, or
- Deprecate it and have the Pi rely on a different mechanism.

**Impact:** Pi clients receive an undocumented event. No breakage currently, but cross-subsystem consumers cannot type-check against it.


### `browser_transcript` event not in contracts

`backend/app/main.py` handles a `browser_transcript` event type on the `/ws/pi` endpoint. This event is not in `contracts/websocket-events.md` (Pi → backend table). It appears to be a browser-side audio transcript shortcut used in the laptop live-check flow. The handler was NOT removed (it is live functionality). The orchestrator should either:
- Add it to contracts as an official Pi → backend event, or
- Move it to the `/ws/phone` endpoint where it arguably belongs semantically.

**Impact:** No breakage, but the Pi contract is underdocumented for this event type.


---

## Localhost inventory

| Location | Value | Disposition |
|----------|-------|-------------|
| `backend/app/config.py` `mongo_url` default | `mongodb://localhost:27017` | **Intentional** — Mongo runs on same host as backend. |
| `backend/app/main.py` CORS (before fix) | `http://localhost:3000`, `http://localhost:8000` | **Fixed** — replaced by `CORS_ORIGINS` env var. |
| `backend/app/scripts/sim_pi.py` `--url` default (before fix) | `ws://localhost:8000/ws/pi/dev-pi` | **Fixed** — updated to Tailscale IP with query-param auth. |
| `backend/app/scripts/verify_e2e.py` `--base-url` default (before fix) | `http://127.0.0.1:8000` | **Fixed** — updated to `http://100.76.124.67:8000`. |

# pi Review

Auditor: WRITER agent, 2026-05-02
Ground truth: contracts/websocket-events.md, contracts/rest-api.md, contracts/schemas/*.schema.json, pi/README.md, pi/HARDWARE.md

---

## Issues found

### [FIXED] Localhost fallbacks in config.py

**File:** `larpchekr/config.py` lines 27–31

`LARPCHEKR_BACKEND_WS` defaulted to `ws://localhost:8000/ws/pi` and `LARPCHEKR_BACKEND_REST` defaulted to `http://localhost:8000`. The Pi is on the Tailscale mesh and the backend is at `100.76.124.67:8000`; localhost would always fail on a real deployment.

**Change:** defaults updated to `ws://100.76.124.67:8000/ws/pi` and `http://100.76.124.67:8000`.

---

### [FIXED] pi/.env.example missing / wrong URLs

**File:** `pi/.env.example`

The file existed but contained the public production URLs (`wss://api.larpchekr.app/ws/pi`, `https://api.larpchekr.app`) rather than Tailscale dev IPs. It also lacked section comments and had `LARPCHEKR_DEVICE_ID=rpi-dev-001` rather than `rpi-001`.

**Change:** rewrote the file with Tailscale IPs, corrected device ID, and added comments per spec.

---

### [CONFIRMED OK] WS auth — query param usage

**File:** `larpchekr/ws_client.py` line 66

The URL is built as `f"{ws_url}?token={token}"` — token is appended as a `?token=` query param. This matches the contract (`wss://…/ws/pi?token=<pi_token>`). No change needed.

---

### [FIXED] Empty contracts/generated/ — WS types not generated

**Files:** `larpchekr/contracts/generated/ws_envelope.py` (new), `larpchekr/contracts/generated/ws_events.py` (new), `larpchekr/contracts/generated/__init__.py` (new), `Makefile`

`contracts/generated/` was empty. The Makefile's `contracts` target tried to generate from the entire `../contracts/schemas/` directory, but `datamodel-codegen 0.25.6` fails on that directory because `profile-facts.schema.json` has a hyphen in its filename, producing invalid Python (`from ..profile-facts import ...`).

**Action taken:**
- Generated `ws_envelope.py` via `datamodel-codegen` from `ws-envelope.schema.json` alone (succeeds).
- Wrote `ws_events.py` manually with a header comment declaring it manually maintained, covering all Pi-relevant event payloads (sends: `PiHello`, `SessionStart`, `SessionEnd`, `AudioMeta`, `FrameSnapshot`, `Heartbeat`, `BufferDrainBracket`; receives: `HapticPulse`, `RecordingIndicator`, `SessionAck`, `ErrorPayload`).
- Added `__init__.py` to make the generated package importable.
- Updated `Makefile` `contracts` target to generate only `ws_envelope.py` and document the limitation.

**Out of scope — orchestrator decision needed:** Rename `contracts/schemas/profile-facts.schema.json` to `profile_facts.schema.json` (and update all `$ref` pointers) to unblock full codegen. This requires updating `ws-events.schema.json`, backend, web-phone, and dashboard consumers in one PR.

---

### [FIXED] LED state machine — WS disconnect sets wrong state

**File:** `larpchekr/ws_client.py` lines 136–145

In the `run()` reconnect loop's `finally` block, every disconnect (including mid-retry) called `self._led.set_state("offline")` (red). Per the README, `offline` (red) means "no network, not recording" — i.e. a terminal state. During a reconnect cycle the Pi is still buffering audio; the correct state is `degraded` (yellow).

**Change:** the `finally` block now sets `degraded` when retrying and `offline` only when `self._stop.is_set()` (i.e. the application is shutting down).

---

### [FIXED] LED state machine — recording_indicator dispatch crashes on unknown state

**File:** `larpchekr/ws_client.py` `_dispatch` method

If the backend sent a `recording_indicator` with an unrecognised `state` value, the call to `self._led.set_state(state)` would raise `ValueError` inside `_dispatch`, propagating up to `_receiver` and terminating the receive loop.

**Change:**
1. Added explicit guard: if `state not in ("off", "armed", "recording")` log a warning and return.
2. Wrapped the entire `_dispatch` call in `try/except Exception` with `log.exception(...)` so a future unexpected error in dispatch cannot kill the receive loop.

---

### [FIXED] REST /pi/claim request body mismatch

**File:** `larpchekr/pairing.py` lines 104–105

The Pi sent `{ "token": ..., "device_id": ... }` but `contracts/rest-api.md` specifies `{ "pair_token": ..., "device_id": ..., "firmware_version": ... }`.

**Change:** field renamed `token` → `pair_token`, added `"firmware_version": "0.1.0"`.

---

### [FIXED] gpiozero version pin non-existent on PyPI

**File:** `requirements.txt` line 5

`gpiozero==2.0.1` does not exist on PyPI (latest release is `2.0`); `pip install` fails with `No matching distribution found`.

**Change:** pinned to `gpiozero==2.0`.

---

### [FIXED] Ruff lint — unused imports, style violations

**Files:** `larpchekr/audio.py`, `larpchekr/buffer.py`, `larpchekr/camera.py`, `larpchekr/ws_client.py`, `larpchekr/config.py`, `larpchekr/hardware/button.py`, `larpchekr/contracts/generated/ws_events.py`

`ruff check` reported 30 issues, of which 24 were auto-fixable and 6 manual:

Auto-fixed (via `ruff check --fix`):
- `UP035`: use `collections.abc` for `Callable`, `Awaitable`, `Iterator` in `audio.py`, `buffer.py`, `camera.py`, `ws_client.py`.
- `UP017`: use `datetime.UTC` alias in `audio.py`, `camera.py`, `ws_client.py`.
- `UP037`: remove unnecessary string quotes from type annotations in `ws_client.py`, `audio.py`, `camera.py`.
- `UP041`: use `TimeoutError` directly in `audio.py`.
- `I001`: unsorted import blocks in `audio.py`, `ws_events.py`.
- `F401` (auto): `websockets` imported but unused in `ws_client.py._receiver` (import was inside `_receiver` but `websockets` was actually used in `_connect_and_run`; auto-fix removed the inner unused one).
- `F401` (auto): `numpy` unused in `_encode_jpeg`, `cv2` unused in `snapshot()` in `camera.py`.
- `UP007`, `UP006`, `UP035` in generated `ws_envelope.py`.

Manual fixes:
- `E501`: wrapped long lines in `camera.py` `_make_snapshot_envelope`, `hardware/button.py`, `ws_client.py` `send_session_end` and `pi_hello` payload.
- `B904`: `raise RuntimeError(...)` in `config.py` `pi_token` property now uses `raise ... from None`.

---

### [FLAGGED] `asyncio.ensure_future` for haptic dispatch

**File:** `larpchekr/ws_client.py` line 265

`asyncio.ensure_future(self._haptic.pulse(pattern, severity))` creates a fire-and-forget task. If `haptic.pulse` raises, the exception is silently swallowed. Not immediately broken, but a pattern to watch: add a `done_callback` that logs exceptions if haptic errors matter.

Not auto-fixed — the existing pattern works and the haptic driver's `pulse` method has broad exception handling internally; flagged for awareness.

---

### [FLAGGED] `heartbeat` `battery_pct` is always 100

**File:** `larpchekr/ws_client.py` line 283

`"battery_pct": 100` is a stub comment `# stub — no battery sensor in v1`. This is intentional and noted in the code. No fix required, but confirm the backend/phone do not use this value for critical decisions.

---

### [FLAGGED] Makefile `contracts` target does not fully generate ws_events.py

**File:** `pi/Makefile`

The `contracts` Makefile target regenerates only `ws_envelope.py`. `ws_events.py` is manually maintained because `datamodel-codegen` cannot process the full schema directory. The Makefile comment explains this. Resolution requires renaming `contracts/schemas/profile-facts.schema.json` — see the "Out of scope" section below.

---

## Out of scope — orchestrator decision needed

### Rename profile-facts.schema.json → profile_facts.schema.json

The hyphen in `contracts/schemas/profile-facts.schema.json` breaks `datamodel-codegen` for the Pi (and likely backend). Renaming requires:
1. Updating the filename.
2. Updating all `$ref` values that reference `profile-facts.schema.json` in other schemas.
3. Regenerating types in backend, web-phone, dashboard, and pi in the same PR.
This is a cross-subsystem change and needs an orchestrator decision.

---

## Localhost inventory

| Location | Value | Disposition |
|----------|-------|-------------|
| `larpchekr/config.py` `LARPCHEKR_BACKEND_WS` default | `ws://localhost:8000/ws/pi` | **FIXED** → `ws://100.76.124.67:8000/ws/pi` |
| `larpchekr/config.py` `LARPCHEKR_BACKEND_REST` default | `http://localhost:8000` | **FIXED** → `http://100.76.124.67:8000` |
| `pi/.env.example` `LARPCHEKR_BACKEND_WS` | `wss://api.larpchekr.app/ws/pi` | **FIXED** → `ws://100.76.124.67:8000/ws/pi` |
| `pi/.env.example` `LARPCHEKR_BACKEND_REST` | `https://api.larpchekr.app` | **FIXED** → `http://100.76.124.67:8000` |

No remaining localhost or 127.0.0.1 references in source code.

---

## LED state machine

All five states implemented in `larpchekr/hardware/led.py`:

| State | Colour (R,G,B) | Trigger |
|-------|----------------|---------|
| `off` | (0,0,0) | Initial / `led.close()` / session ended |
| `armed` | Blue (0,0,1) | WS connected, waiting for session |
| `recording` | Green (0,1,0) | `recording_indicator` state=recording |
| `degraded` | Yellow (1,1,0) | WS disconnect, mid-retry (FIXED) |
| `offline` | Red (1,0,0) | `_stop` set (shutdown) |

Driving logic (after fix):
- `main.py:105`: startup → `offline`
- `ws_client.py._connect_and_run:170`: on connect → `armed`
- `ws_client.py._dispatch recording_indicator=recording` → `recording` (green = consent indicator)
- `ws_client.py._dispatch recording_indicator=armed` → `armed`
- `ws_client.py._dispatch recording_indicator=off` → `off`
- `ws_client.py.run finally` (mid-retry): → `degraded` (yellow) **[was: offline — FIXED]**
- `ws_client.py.run finally` (stop set): → `offline` (red)

Contract `recording_indicator.state` values `"off" | "armed" | "recording"` all handled. Unknown state values now logged and ignored (no crash).

---

## Contract conformance

### WS event types — Pi → backend

| Contract type | Code location | Conforms? |
|---------------|---------------|-----------|
| `pi_hello` | `ws_client.py:_connect_and_run` | Yes |
| `session_start` | `ws_client.py:send_session_start` | Yes |
| `session_end` | `ws_client.py:send_session_end` | Yes |
| `audio_meta` | `audio.py:_make_audio_meta_envelope` | Yes |
| `(binary PCM)` | `audio.py:send_binary` | Yes — 8-byte header + PCM |
| `frame_snapshot` | `camera.py:_make_snapshot_envelope` | Yes |
| `heartbeat` | `ws_client.py:heartbeat_loop` | Yes |
| `buffer_drain_start` | `ws_client.py:_drain_buffer` | Yes |
| `buffer_drain_end` | `ws_client.py:_drain_buffer` | Yes |

### WS event types — backend → Pi

| Contract type | Handled in | Conforms? |
|---------------|------------|-----------|
| `haptic_pulse` | `ws_client.py:_dispatch` | Yes — severity + pattern used |
| `recording_indicator` | `ws_client.py:_dispatch` | Yes — drives LED; validated state values |
| `session_ack` | `ws_client.py:_dispatch` | Yes |
| `error` | `ws_client.py:_dispatch` | Yes — code + message logged |

### REST endpoints

| Contract endpoint | Pi usage | Conforms? |
|-------------------|----------|-----------|
| `POST /pi/claim` | `pairing.py:_claim` | **FIXED** — was sending `token`, now `pair_token`; added `firmware_version` |

### Envelope fields

The `ws-envelope.schema.json` requires `id`, `type`, `ts`, `data`. All Pi-constructed envelopes include these fields. `session_id` is optional and correctly omitted before a session is active.

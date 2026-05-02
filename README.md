# L4RPCH3KR

A wearable + app system that detects claims people make during hackathon conversations, cross-references them against verifiable signals (GitHub, LinkedIn, organizer-provided attendee data), and surfaces discrepancies in real time as a "larp score."

## System overview

Three subsystems plus an organizer dashboard:

- **Pi capture device** — chest-worn Raspberry Pi 5 with USB camera/mic and a haptic motor. Captures audio + occasional video frames, streams to backend, vibrates when a flag fires.
- **Phone app** — React Native (iOS + Android). Onboarding, live mode (status pill + flag cards), recap screen.
- **Backend** — FastAPI server. The brain: transcription, speaker separation, claim extraction, profile comparison, scoring, websocket fan-out. MongoDB.
- **Organizer dashboard** — Next.js. CSV import of attendees with profile-link enrichment, CRUD, export.

## Architecture

```
                   ┌─────────────────────────┐
                   │   Backend (FastAPI)     │
                   │                         │
   audio/frames    │  ┌──────────────────┐   │   flags / haptic
  ──────────────►  │  │ ASR (Whisper)    │   │  ──────────────────
   ws://.../pi     │  │ Diarization      │   │   ws://.../phone
                   │  │ Claim extraction │   │
                   │  │ Profile compare  │   │   ws://.../pi (back)
                   │  │ Scoring          │   │
                   │  └──────────────────┘   │
                    │        MongoDB          │
                   └────┬───────────────┬────┘
                        │               │
                        │ REST          │ REST
                        ▼               ▼
                ┌──────────────┐  ┌──────────────────┐
                │ Phone (RN)   │  │ Dashboard (Next) │
                └──────────────┘  └──────────────────┘
```

Three websocket connections per active session: Pi↔backend, phone↔backend (one per attendee). Phone and Pi never talk to each other.

## Data flow (one larp catch)

1. Pi: VAD detects speech → streams 16kHz PCM frames + occasional JPEG snapshots over websocket.
2. Backend: buffers audio → faster-whisper transcribes → speaker embedding matches each utterance against the user's calibrated voice → tags `self` or `partner`.
3. On a complete `partner` utterance, the backend runs claim extraction (LLM with structured output) → resolves `partner_id` (see "Face → identity" below) → fetches cached profile → compares claims to profile facts → emits `flag_raised` if a discrepancy passes the confidence threshold.
4. Backend → phone: `flag_raised` event. Phone shows slide-in card.
5. Backend → Pi: `haptic_pulse` event. Pi triggers GPIO motor.
6. Latency budget end-to-end: <4s utterance-end → haptic. Realistically tight; see "Known unknowns."

## Tech stack

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | **Python 3.11 + FastAPI** | Native fit with faster-whisper, pyannote, the LLM SDKs. Async websockets via Starlette. Faster to wire than splitting Node↔Python for ML. |
| DB | **MongoDB 7** | Attendees, claims, flags, sessions, profile facts, and voice calibration docs. |
| ASR | **faster-whisper** (`small.en` initial, `medium.en` if budget allows) | Runs on backend GPU, not the Pi. CTranslate2 backend is fast enough for near-real-time. |
| Diarization | **speechbrain ECAPA-TDNN** speaker embeddings + cosine match | Lightweight; pairs well with onboarding voice calibration. |
| Claim extraction | **LLM with structured output** (Anthropic Claude Sonnet 4.6 or OpenAI gpt-4.1-mini, structured JSON via tool-use) | Casual speech is too messy for rules+NER. Latency budget allows ~1.5s. |
| Pi | **Python 3.11**, `sounddevice`, `opencv-python`, `websockets`, `RPi.GPIO` | Single language for the device team, well-supported on Pi 5. |
| Phone | **React Native + TypeScript** (bare RN, not Expo Go — we need native haptics + BLE-ish reliability for Pi pairing flows) | One codebase, iOS+Android. Bare RN gives us the dev-client flexibility without Expo's prebuild costs. Reconsider Expo dev client if onboarding pain dominates. |
| Dashboard | **Next.js 15 (App Router) + TypeScript** | Same TS toolchain as phone for shared types. SSR not strictly required but useful for the org-internal dashboard. |
| Auth | **Magic link** for attendees (email-only) + **GitHub OAuth** as a separate connect-step in onboarding | Hackathon-grade simplicity. GitHub login conflates auth with profile-linking; we want them separate. |
| Deploy (demo) | Backend + dashboard on Fly.io or Railway, MongoDB managed | One region, ship fast. |

If a teammate disagrees, edit this table in a PR and explain why.

## Shared contracts

The seams between subsystems live in [`contracts/`](./contracts/README.md). Read this folder before writing any inter-subsystem code:

- `contracts/websocket-events.md` — every WS message shape, direction, and trigger condition.
- `contracts/rest-api.md` — every REST endpoint, request/response, auth posture.
- `contracts/data-models.md` — the canonical entity definitions (User, Event, Attendee, Session, Utterance, Claim, Flag, Profile).
- `contracts/schemas/*.schema.json` — JSON Schema files. Source of truth. Backend generates Pydantic models from these; phone + dashboard generate TS types via `json-schema-to-typescript`.

**Rule:** any change to a schema requires updating all consumers in the same PR. A changed schema with no downstream updates is a broken build.

## Build order

To unblock parallel work, build in this order:

1. **Day 0 (joint):** finalize `contracts/`. Lock schemas. Generate types into each subsystem.
2. **Day 1:**
   - Backend: stub WS endpoints that echo schemas; stub REST endpoints with fixture responses.
   - Phone: onboarding screens (1–4) against placeholder design tokens.
   - Pi: audio capture + WS connect + heartbeat. No ASR yet.
   - Dashboard: CSV import UI + attendee table against fixture API.
   - Designer: lock design tokens, deliver onboarding screens.
3. **Day 2:**
   - Backend: real ASR + diarization. Emits fake `flag_raised` on every 3rd partner utterance for integration testing.
   - Phone: live mode renders flag cards from real WS.
   - Pi: haptic on `haptic_pulse`. Camera frames optional.
   - Designer: live mode + flag card.
4. **Day 3:**
   - Backend: real claim extraction + profile compare.
   - Phone: recap screen.
   - Designer: recap screen + dashboard.
5. **Day 4:** end-to-end demo loop. Polish only.

## Team assignments

| Person | Owns |
|--------|------|
| Engineer A | `pi/` — audio/camera capture, haptic, enclosure-fit, BLE/QR pairing client, on-device VAD |
| Engineer B | `backend/` + `dashboard/` — server end-to-end, including organizer tools. Shared deploy target. |
| Engineer C | `phone/` — RN app, all three flows (onboarding, live, recap) |
| Designer | `design/` — Figma source, design tokens export, asset export, all locked-scope screens |

If contracts shift such that B has too much, peel `dashboard/` off to a fourth engineer or have C take it on once the phone live mode stabilizes.

## Known unknowns and risks

These are real and should be revisited weekly. Each has a proposed MVP path and a fallback.

### 1. Face → LinkedIn lookup
There is no clean API. Options:
- **(MVP recommendation)** Skip face recognition. Identify the conversation partner via a **QR-code handshake**: both attendees have the L4RPCH3KR app, one scans the other's "I'm here" QR, the backend pairs them for the session. Fallback for one-sided conversations: organizer-provided attendee list + Bluetooth proximity ranking.
- (Later) Paid reverse-image services (PimEyes etc.) — has cost, ethical, and ToS issues.
- (Later) Opt-in only: organizer uploads photos for attendees who waiver-consent, backend uses on-device face embedding match.

### 2. Consent and recording laws
Two-party consent states (CA, FL, IL, MA, MD, MT, NH, PA, WA), GDPR jurisdictions, etc. MVP requirements:
- Pi has a **visible recording LED** at all times when streaming.
- Pairing flow includes the partner's **explicit opt-in** ("I consent to be recorded for this hackathon demo") on their phone.
- Posture: **demo mode only, hackathon attendees who signed the event waiver.** Hard-coded refusal to record without partner pairing in v1.
- Recordings are deleted from disk within 24h of the session end. Transcripts retained per the event's retention policy (set by organizer).

### 3. Claim extraction quality
Casual hedges ("kinda", "I've worked with") are the main failure mode. Approach:
- LLM with structured output (Anthropic / OpenAI tool-use), schema in `contracts/schemas/claim.schema.json`.
- The schema includes a `hedge` enum: `none | weak | strong`. Flags are suppressed when `hedge != none` unless the discrepancy is severe (e.g. claimed shipping prod Rust vs. zero Rust on GitHub).
- Latency target: utterance-end → flag emitted ≤ 4s. Of that: ASR ≤ 1.5s, claim extraction ≤ 1.5s, profile compare ≤ 0.5s, network ≤ 0.5s.
- Fallback if LLM call exceeds 2s: emit a low-confidence flag based on keyword + profile signal alone.

### 4. Speaker separation
Voice calibration in onboarding records 15s of the user's speech, computes an ECAPA-TDNN embedding, and stores it. Each utterance the backend extracts an embedding and cosine-matches:
- match > 0.7 → `self`
- match < 0.4 → `partner`
- between → `unknown`, drop the utterance from claim extraction (don't flag user's own claims for now).

Failure cases: noisy room, partner sounds similar, user has a cold. We will tag every flag with `partner_speaker_confidence` so the recap screen can de-emphasize uncertain ones.

### 5. Offline / degraded behavior
Hackathon wifi WILL die. The Pi:
- Buffers audio locally (ring buffer, ~5 min) when WS is down.
- LED turns yellow when degraded, red when fully offline (not recording).
- On reconnect, drains the buffer to backend. Latency for flags during outage = duration of outage; that's acceptable.

The phone:
- Shows "connection lost" pill, freezes the live feed.
- Recap will be available once backend processes the buffer.

## Repo structure

```
L4RPCH3KR/
├── README.md                  ← you are here
├── contracts/                 ← shared schemas, READ FIRST
├── pi/                        ← Engineer A
├── backend/                   ← Engineer B
├── dashboard/                 ← Engineer B
├── phone/                     ← Engineer C
├── design/                    ← Designer
└── infra/                     ← deploy notes
```

## Local dev (full stack)

Each subsystem has its own README with setup. To run the whole loop locally you need: MongoDB, the backend, the dashboard, the phone (simulator or device), and either a real Pi or the Pi-simulator script in `backend/scripts/sim_pi.py` (TBD).

## Open questions (top-level)

- Which LLM provider for claim extraction — Anthropic Claude Sonnet 4.6 vs. OpenAI gpt-4.1-mini? Decide on day 0 based on whoever has API credit available.
- Hosting: Fly.io vs. Railway vs. self-hosted? Engineer B's call by end of day 1.
- Do we ship the dashboard as part of the demo, or is it organizer-only and pre-loaded? If organizer-only, deprioritize polish.
- Pi enclosure: who's printing it? Lead time on the print is the longest physical dependency.

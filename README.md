# L4RPCH3KR

L4RPCH3KR is a wearable + web system built for **EurekaHacks 2026** in **under 24 hours**. It listens to hackathon conversations, extracts technical claims, compares them against verifiable profile signals, and surfaces suspicious mismatches as real-time flags and a larp score.

## Team

Built by:

| Team member | GitHub |
|-------------|--------|
| Arnnav Kudale | [`blazecoding2009`](https://github.com/blazecoding2009) |
| Aditya Choudhuri | [`Bot-106`](https://github.com/Bot-106) |
| Abhimanyu Chaudhary | [`MadRobin13`](https://github.com/MadRobin13) |
| Wenya Wang | [`eve-ite`](https://github.com/eve-ite) |

## What It Does

- Captures audio and optional camera frames from a Raspberry Pi wearable.
- Streams session events to a FastAPI backend over websockets.
- Extracts claims from conversation transcripts with an LLM pipeline.
- Compares claims against attendee data, GitHub signals, and LinkedIn/profile context.
- Raises discrepancy flags in real time.
- Sends haptic pulses back to the wearable when a flag fires.
- Shows attendees a phone-friendly live mode and recap flow.
- Gives organizers a dashboard for events, attendees, imports, exports, flags, and the Larperboard.

## System Overview

```
                 audio / frames                  flags / haptic
Raspberry Pi  ------------------>  FastAPI  <------------------  Web Phone
 wearable          /ws/pi          backend          /ws/phone       PWA
                                      |
                                      | REST
                                      v
                              Next.js Dashboard
                                      |
                                      v
                                   MongoDB
```

The Pi and phone never talk directly. The backend owns session state, transcript ingestion, claim extraction, profile comparison, score updates, and websocket fan-out.

## Subsystems

| Path | Purpose |
|------|---------|
| [`backend/`](./backend/README.md) | FastAPI API, websockets, MongoDB persistence, claim extraction, profile comparison, flags, and scoring. |
| [`dashboard/`](./dashboard/README.md) | Next.js organizer dashboard for events, attendees, CSV import/export, flags, and the Larperboard. |
| [`web-phone/`](./web-phone/README.md) | React/Vite attendee PWA for onboarding, pairing, live flag cards, and recap. |
| [`pi/`](./pi/README.md) | Raspberry Pi capture client for audio/frame streaming and haptic feedback. |
| [`contracts/`](./contracts/README.md) | Shared REST, websocket, data model, and JSON schema contracts. |
| [`design/`](./design/) | Arcade visual system, design tokens, and UI references. |

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | Python 3.11, FastAPI, Starlette websockets, MongoDB, pytest |
| AI pipeline | Anthropic/OpenAI-compatible LLM structured extraction, profile comparison, scoring |
| Dashboard | Next.js 15 App Router, TypeScript, custom arcade CSS system |
| Phone app | Vite, React, TypeScript, Zustand, TanStack Query, Framer Motion |
| Pi client | Python 3.11, websockets, sounddevice, OpenCV, GPIO/haptic hooks |

## Key Features

- Event creation and organizer sign-in.
- CSV attendee import and enriched CSV export.
- Manual attendee creation and inline attendee editing.
- GitHub and LinkedIn/profile comparison summaries.
- Event-level flags view.
- Global Larperboard with optional event filtering.
- Pi websocket session handling and disconnect-safe cleanup.
- Phone websocket live mode with flag cards and recap screens.
- Arcade-styled dashboard built from the L4RPCH3KR design direction.

## Local Development

Run each subsystem from its own folder:

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd dashboard
npm install
npm run dev
```

```bash
cd web-phone
npm install
npm run dev
```

The backend expects MongoDB and the required API keys/env vars from `backend/.env.example`. The dashboard and phone apps point at the backend with their local `.env` files.

## Verification

Useful checks:

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest
```

```bash
cd dashboard
npm run typecheck
npm run build
```

## Status

This is a hackathon demo implementation, not a production surveillance product. Consent, recording indicators, event policy, and data retention need to be handled carefully before any real-world use.

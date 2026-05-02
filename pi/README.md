# pi/ - Capture Device

Raspberry Pi wearable client for L4RPCH3KR. It captures session audio and optional camera frames, streams them to the backend, and triggers haptic feedback when the backend raises a flag.

## Scope

- Connect to the backend Pi websocket at `/ws/pi`.
- Send session lifecycle events, transcript/audio payloads, frame snapshots, and heartbeats.
- Receive `haptic_pulse`, `recording_indicator`, `session_ack`, and `error` events.
- Drive haptic feedback through GPIO-compatible hardware hooks.
- Support fake hardware mode for local development without a Pi.

## Hardware Target

| Component | Spec |
|-----------|------|
| SBC | Raspberry Pi 5 |
| Mic | USB mic or webcam mic |
| Camera | USB webcam or Pi-compatible camera |
| Haptic | Small DC motor through GPIO driver circuit |
| Indicator | Visible LED for recording/connection state |

## Running On A Pi

```bash
cd pi
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m larpchekr.main
```

## Local Fake Hardware Mode

```bash
cd pi
LARPCHEKR_FAKE_HARDWARE=1 python -m larpchekr.main
```

## Environment

| Var | Purpose |
|-----|---------|
| `LARPCHEKR_BACKEND_WS` | Backend websocket URL, for example `ws://localhost:8000/ws/pi` |
| `LARPCHEKR_BACKEND_REST` | Backend REST origin |
| `LARPCHEKR_PI_TOKEN_PATH` | Path for the persisted Pi token |
| `LARPCHEKR_DEVICE_ID` | Stable device identifier |
| `LARPCHEKR_FAKE_HARDWARE` | Enables mocked GPIO/audio/camera paths for development |

## Safety Note

The recording indicator should be visible whenever the device is actively streaming. This project was built as a hackathon demo and should not be used for real recording without explicit consent and a clear retention policy.

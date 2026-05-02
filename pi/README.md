# pi/ — Capture device

Owner: **Engineer A**.

The chest-worn capture device. Streams audio + occasional video frames to the backend, vibrates the haptic motor on `haptic_pulse` events, drives the recording-indicator LED.

## Scope

In:
- USB mic audio capture (16kHz mono PCM s16le, 250ms frames).
- Local VAD (voice activity detection) — only stream when there's speech.
- USB camera frame snapshot every 10s.
- WS connection to backend (`/ws/pi`), reconnect with backoff.
- Local ring buffer for offline degradation.
- GPIO haptic motor (single-channel PWM).
- LED state machine: off / armed / recording / degraded / offline.
- Pairing flow: read pair-token from a phone-displayed QR using the camera, POST to `/pi/claim`.
- Hardware-side fit: enclosure mounting, cable routing, button for manual session-start/stop.

Out (v1):
- On-device ASR.
- Speaker separation.
- Any kind of cloud inference from the Pi directly.
- Battery management beyond reporting `battery_pct` if the power source exposes it.

## Hardware

| Component | Spec |
|-----------|------|
| SBC | Raspberry Pi 5, 16GB RAM |
| Mic | Logitech USB camera (built-in mic) |
| Camera | Same Logitech USB |
| Haptic | Small DC motor via N-MOSFET on GPIO18 (PWM) |
| LED | Single RGB LED on GPIO12/13/16 |
| Button | Momentary, GPIO22, pull-up |
| Enclosure | 3D-printed chest mount (designer + Engineer A) |

GPIO pin table is duplicated in `pi/HARDWARE.md` (TBD — Engineer A writes this on day 1).

## Tech stack

- **Python 3.11**
- `sounddevice` for audio capture (lower latency than PyAudio on Pi 5)
- `opencv-python-headless` for camera frames
- `websockets` (async client)
- `RPi.GPIO` or `gpiozero` for motor + LED + button (gpiozero preferred for cleaner abstractions)
- `webrtcvad` for VAD
- `pyzbar` for QR code reading during initial pair

## File layout

```
pi/
├── README.md
├── HARDWARE.md                ← pinout, wiring, LED state table (Engineer A)
├── pyproject.toml
├── requirements.txt
├── larpchekr/
│   ├── __init__.py
│   ├── main.py                ← entrypoint, runs the event loop
│   ├── config.py              ← env vars, paths
│   ├── audio.py               ← sounddevice capture + VAD
│   ├── camera.py              ← opencv frame snapshots
│   ├── ws_client.py           ← websocket connect/reconnect, send/recv
│   ├── buffer.py              ← ring buffer for offline degradation
│   ├── hardware/
│   │   ├── __init__.py
│   │   ├── haptic.py          ← motor driver
│   │   ├── led.py             ← LED state machine
│   │   └── button.py          ← debounced input
│   ├── pairing.py             ← QR-scan pair flow
│   └── contracts/
│       └── generated/         ← from /contracts (gitignored)
├── scripts/
│   ├── pair.py                ← one-shot pair helper
│   ├── vad_test.py            ← local VAD debugging
│   └── haptic_test.py         ← motor smoke test
└── tests/
    └── test_buffer.py
```

## External interfaces

### Consumes
- WS messages from backend per `contracts/websocket-events.md`:
  - `haptic_pulse`
  - `recording_indicator`
  - `session_ack`
  - `error`
- REST `POST /pi/claim` once during initial pairing.

### Exposes (sends to backend)
- WS messages per `contracts/websocket-events.md`:
  - `pi_hello`, `session_start`, `session_end`
  - `audio_meta` (JSON) + binary PCM frames
  - `frame_snapshot`
  - `heartbeat`
  - `buffer_drain_start`, `buffer_drain_end`

### Local environment
Reads from `pi/.env`:

| Var | Required | Example |
|-----|----------|---------|
| `LARPCHEKR_BACKEND_WS` | yes | `wss://api.larpchekr.app/ws/pi` |
| `LARPCHEKR_BACKEND_REST` | yes | `https://api.larpchekr.app` |
| `LARPCHEKR_PI_TOKEN_PATH` | yes | `/etc/larpchekr/pi_token` |
| `LARPCHEKR_DEVICE_ID` | yes | `rpi-001` |
| `LARPCHEKR_LOG_LEVEL` | no | `info` |

## Local setup

On the Pi:

```bash
sudo apt install -y python3.11 python3.11-venv python3-pip libportaudio2 libzbar0
git clone <repo> && cd L4RPCH3KR/pi
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make contracts          # regen schemas
sudo cp scripts/larpchekr.service /etc/systemd/system/
sudo systemctl enable --now larpchekr
```

Off the Pi (dev on laptop, mocked hardware):

```bash
LARPCHEKR_FAKE_HARDWARE=1 python -m larpchekr.main
```

`FAKE_HARDWARE=1` swaps in stubs for GPIO + camera + audio so you can iterate the WS protocol without a Pi.

## MVP checklist

- [ ] Audio capture at 16kHz mono, 250ms frames, latency <50ms.
- [ ] VAD gates streaming (no audio sent during silence).
- [ ] WS connect with auth, send `pi_hello`, receive `session_ack`.
- [ ] Frame snapshot every 10s, ≤640×480 JPEG.
- [ ] Heartbeat every 10s.
- [ ] Haptic motor responds to `haptic_pulse` with the correct pattern.
- [ ] LED state machine reflects connection + recording state.
- [ ] Offline buffering: WS drops → buffer locally → drain on reconnect.
- [ ] QR-pair flow: scan phone QR, POST to `/pi/claim`, persist `pi_token`.
- [ ] Manual button starts/ends session (only after a session has been armed via the phone).
- [ ] Recording-indicator LED is **always** visible when streaming. This is non-negotiable for consent.

## Non-goals

- Encryption beyond TLS (no on-device E2E).
- Battery monitoring UI.
- OTA updates for the Pi software (manual `git pull` is fine for v1).
- Multi-mic / beamforming.
- Multi-user device sharing.
- Detection of the user removing the device (we may add a tilt sensor in v2).

## Open questions

- **Pi 5 audio thermal:** does the Pi 5 throttle under continuous capture + WS? Engineer A: stress-test on day 1 with `vcgencmd measure_temp`.
- **Camera framerate budget:** 1 frame / 10s is conservative. Can we afford more if we don't transmit them? Probably yes, but 10s is plenty for v1.
- **Pair-token storage:** plaintext in `/etc/larpchekr/pi_token` is fine for hackathon; lock down with file permissions. Real product would use TPM / Pi 5 security extensions.
- **Enclosure microphone occlusion:** the print needs an open grille over the mic. Coordinate with the designer before printing.

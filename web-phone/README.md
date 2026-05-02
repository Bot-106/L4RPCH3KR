# web-phone/ - Attendee PWA

Attendee-facing progressive web app for L4RPCH3KR, built for the EurekaHacks 2026 demo. It runs in a mobile or desktop browser and connects to the FastAPI backend for onboarding, pairing, live flags, score updates, and recap.

## Scope

- Magic-link sign-in callback flow.
- GitHub connect step.
- Voice calibration screen.
- Pi pairing QR flow.
- Partner QR show/scan flow.
- Live session screen with connection state, larp score, and flag cards.
- Recap screen with post-session flags.
- Websocket client with reconnect/backoff behavior.

## Running Locally

```bash
cd web-phone
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:3000` or your local network/Tailscale URL for mobile testing.

## Environment

```bash
VITE_API_BASE=http://localhost:8000
VITE_WS_BASE=ws://localhost:8000
```

## Screens

| Route | Screen | Description |
|-------|--------|-------------|
| `/onboarding/signin` | SignInScreen | Enter email for auth |
| `/auth/callback` | AuthCallbackScreen | Persist token and route to onboarding |
| `/onboarding/github` | GithubConnectScreen | Link GitHub account |
| `/onboarding/voice` | VoiceCalibrationScreen | Record calibration audio |
| `/onboarding/pair` | PiPairScreen | Show QR for Pi pairing |
| `/live` | LiveScreen | Live status, score, and flag cards |
| `/pair/show` | ShowQrScreen | Display partner pairing QR |
| `/pair/scan` | ScanQrScreen | Scan partner QR |
| `/recap/:sessionId` | RecapScreen | Post-session recap |

## Tech Stack

- Vite + React + TypeScript
- Zustand for auth/session state
- TanStack Query for recap fetches
- Framer Motion for live flag animation
- `jsQR` and `qrcode.react` for QR flows
- Custom websocket client in `src/lib/ws.ts`

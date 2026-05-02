# L4RPCH3KR — Web Phone App

The attendee-facing progressive web app for L4RPCH3KR. Runs in any mobile or desktop browser. Connects to the FastAPI backend over Tailscale.

## Running locally

```bash
cd web-phone
npm install
npm run dev
```

Open `http://localhost:3000` (or your local IP for mobile testing).

## Tailscale configuration

Copy `.env.example` to `.env` and set your Tailscale IP:

```
VITE_API_BASE=http://100.64.x.x:8000
VITE_WS_BASE=ws://100.64.x.x:8000
```

Then access the app from your phone at `http://100.64.x.x:3000`.

## Screens

| Route | Screen | Description |
|-------|--------|-------------|
| `/onboarding/signin` | SignInScreen | Enter email to receive a magic link |
| `/auth/callback` | AuthCallbackScreen | Handles magic-link token, sets JWT, routes to next step |
| `/onboarding/github` | GithubConnectScreen | Link GitHub account via OAuth |
| `/onboarding/voice` | VoiceCalibrationScreen | Record 15s of audio for speaker diarization |
| `/onboarding/pair` | PiPairScreen | QR code for the Raspberry Pi to scan and claim |
| `/live` | LiveScreen | Real-time session view: status pill, larp score, flag cards |
| `/pair/show` | ShowQrScreen | Display a QR code for your partner to scan |
| `/pair/scan` | ScanQrScreen | Scan partner's QR via camera to link session |
| `/recap/:sessionId` | RecapScreen | Post-session flag list with dispute flow |

## Architecture

- **Vite + React 18 + TypeScript** (strict mode)
- **Zustand** for auth state (`authStore`) and session/WS state (`sessionStore`)
- **TanStack Query v5** for the recap data fetch
- **Framer Motion** for flag card slide-in animation
- **jsQR** for camera-based QR decoding
- **qrcode.react** for QR display
- **Custom WSClient** (`src/lib/ws.ts`) with exponential backoff reconnect (1s→30s, ±20% jitter)
- **Design tokens** from `design/tokens/tokens.example.json`, injected as CSS custom properties, consumed via Tailwind theme extension

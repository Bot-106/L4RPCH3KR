# phone/ — React Native app

Owner: **Engineer C**.

The attendee-facing app. iOS + Android from one codebase. Three flows: onboarding, live mode, recap.

## Scope

In:
- **Onboarding** (4 screens):
  1. Sign in (email → magic link).
  2. Connect GitHub (OAuth in-app browser).
  3. Voice calibration (record 15s, upload to backend).
  4. Pi pairing (phone shows QR; Pi scans).
- **Live mode**:
  - Status pill at top: "Armed" / "Recording" / "Disconnected".
  - Slide-in flag card on `flag_raised`. Card shows: claim text, severity color, what the verified source said, dismiss.
  - Quiet by default. No live transcript view (out of v1).
  - Triggers a soft phone haptic on flag (the Pi's haptic is the primary cue; phone is the visual).
- **Partner pairing UI**: scan QR (camera) + show QR (display).
- **Recap**: list of utterances, flag cards expanded with audio playback, dispute button per flag.
- **Auth state**: keychain-backed JWT, auto-refresh, sign-out.

Out (v1):
- Public profile screen.
- Friends / social.
- Push notifications.
- Offline mode beyond "show last cached recap."
- Dark mode (until designer ships tokens).
- Tablet / iPad layout.

## Tech stack

- **React Native 0.74** + **TypeScript** (bare RN, not Expo Go — we need stable native modules)
- **Expo Modules** in bare RN for Camera, Haptics, SecureStore (you can pull individual `expo-*` modules into bare RN; no need for Expo Go)
- **React Navigation** (stack + bottom tabs)
- **Zustand** for app state (small surface; no Redux)
- **TanStack Query** for server state
- **react-native-mmkv** for persisted client state
- **react-native-vision-camera** for QR scan + voice calibration mic capture
- **react-native-svg** for icons
- **react-native-reanimated** + **react-native-gesture-handler** for the flag card animation
- **socket auth via WS:** native `WebSocket` is fine; reconnect logic is custom

## File layout

```
phone/
├── README.md
├── package.json
├── tsconfig.json
├── babel.config.js
├── metro.config.js
├── app.json                   ← RN/Expo modules config (name, bundleId)
├── ios/                       ← native (engineer C maintains)
├── android/                   ← native (engineer C maintains)
├── src/
│   ├── App.tsx
│   ├── navigation/
│   │   ├── RootNavigator.tsx
│   │   └── linking.ts         ← magic-link deep links
│   ├── screens/
│   │   ├── onboarding/
│   │   │   ├── SignInScreen.tsx
│   │   │   ├── GithubConnectScreen.tsx
│   │   │   ├── VoiceCalibrationScreen.tsx
│   │   │   └── PiPairScreen.tsx
│   │   ├── live/
│   │   │   ├── LiveScreen.tsx
│   │   │   ├── StatusPill.tsx
│   │   │   └── FlagCard.tsx
│   │   ├── pair/
│   │   │   ├── ShowQrScreen.tsx
│   │   │   └── ScanQrScreen.tsx
│   │   └── recap/
│   │       ├── RecapScreen.tsx
│   │       ├── FlagDetail.tsx
│   │       └── DisputeSheet.tsx
│   ├── services/
│   │   ├── api.ts             ← typed REST client
│   │   ├── ws.ts              ← WS client w/ reconnect
│   │   └── auth.ts
│   ├── stores/
│   │   ├── session.ts         ← zustand: current session, status, flags
│   │   └── auth.ts
│   ├── theme/
│   │   ├── tokens.ts          ← imports ../design/tokens/tokens.json
│   │   └── ThemeProvider.tsx
│   ├── contracts/
│   │   └── generated/         ← from /contracts (gitignored)
│   ├── components/            ← shared primitives
│   └── lib/
│       ├── haptics.ts
│       └── time.ts
└── tests/
    └── e2e/                   ← detox (TBD if there's time)
```

## External interfaces

### Consumes
- Backend REST per `contracts/rest-api.md`. Auth, onboarding, sessions, flags.
- Backend WS at `/ws/phone` per `contracts/websocket-events.md`.
- Design tokens at `../design/tokens/tokens.json`.
- Asset SVGs at `../design/assets/icons/*.svg`.

### Exposes
- Magic-link deep link handler (`larpchekr://auth?token=...`).
- App-side QR for partner pairing (just a URL/token rendered; backend issues it).

### Local environment
Reads from `phone/.env` (via `react-native-dotenv`):

| Var | Required | Example |
|-----|----------|---------|
| `API_BASE` | yes | `http://10.0.2.2:8000` (Android emulator) / `http://localhost:8000` (iOS sim) |
| `WS_BASE` | yes | `ws://10.0.2.2:8000` |
| `DEEP_LINK_SCHEME` | yes | `larpchekr` |

## Local setup

```bash
cd phone
npm install
npm run contracts
cd ios && pod install && cd ..

# iOS
npm run ios

# Android (emulator must be running)
npm run android
```

To test on a device, the device must reach the laptop's backend — either run backend on a tunnel (cloudflared, ngrok) or wire up a local hostname.

## MVP checklist

- [ ] Onboarding 1: magic-link sign-in completes; JWT in keychain.
- [ ] Onboarding 2: GitHub OAuth in-app browser, returns to user with `github_login` set.
- [ ] Onboarding 3: voice calibration records 15s, uploads, success state.
- [ ] Onboarding 4: Pi pair shows QR; on backend `pi_token` issued, screen advances.
- [ ] Live mode: connects WS, sends `subscribe_session`, status pill reflects `session_status`.
- [ ] Live mode: `flag_raised` triggers slide-in card animation + soft phone haptic.
- [ ] Live mode: card auto-dismisses after 8s, can be tapped to lock open.
- [ ] Partner pairing: scan QR works against the backend's QR token.
- [ ] Recap: full session loads from `GET /sessions/:id/recap`.
- [ ] Recap: tap flag → expanded view → audio plays → dispute button writes via REST.
- [ ] Reconnect logic: WS drops → exponential backoff → recovers without user action.
- [ ] Renders correctly with placeholder design tokens; reskins cleanly when designer ships final tokens.

## Non-goals

- Live transcript display.
- Sharing flags / cards.
- A "claims log" of what the user themself said.
- Notifications when the app is backgrounded.
- Custom keyboards or accessibility audits beyond default RN behavior.

## Open questions

- **Bare RN vs Expo prebuild:** if Engineer C is more comfortable with Expo prebuild, switch — the Expo dev client supports the native modules we need. Decide day 0. Stack table assumes bare RN.
- **iOS background WS:** iOS will kill WS when backgrounded. Live mode is foreground-only by design; surface a clear "backgrounded — paused" state if the user navigates away.
- **Phone haptic intensity:** map `severity` to phone haptic patterns. iOS has finer control than Android; document the chosen mapping in `src/lib/haptics.ts`.
- **Magic-link deep link reliability:** universal links / app links require dev domain setup. For hackathon, fall back to a manual "paste your code" input if the deep link breaks.

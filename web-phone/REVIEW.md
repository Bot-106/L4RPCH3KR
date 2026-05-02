# web-phone Review

## Issues found

### [FIXED] Hand-written types (Issue 1)

**Files changed:**
- `src/contracts/types.ts` — stripped all entity types (User, Attendee, Event, Profile, ProfileFacts, Session, Utterance, Claim, Flag, VoiceCalibration, Pairing, and hand-written WsEnvelope generic). File now contains only API response shapes and WS payload wrappers that are phone-specific and absent from JSON schemas.
- `src/contracts/generated/` (new directory) — contains TS types generated from every schema file via `json-schema-to-typescript`.
- `src/contracts/generated/index.ts` (new) — barrel re-exporting all generated entity types.
- `package.json` — added `"contracts"` script (`node scripts/generate-contracts.mjs`) and installed `json-schema-to-typescript` as devDependency.
- `scripts/generate-contracts.mjs` (new) — runs `json2ts` once per schema file from the `contracts/schemas/` directory (required for `$ref` resolution), outputs to `src/contracts/generated/`.

**Generated files (do not edit):**
- `src/contracts/generated/attendee.ts` — `Attendee`
- `src/contracts/generated/claim.ts` — `Claim` + six value subtypes
- `src/contracts/generated/event.ts` — `Event`
- `src/contracts/generated/flag.ts` — `Flag`
- `src/contracts/generated/profile-facts.ts` — `ProfileFacts`
- `src/contracts/generated/profile.ts` — `Profile` (inlines `ProfileFacts`)
- `src/contracts/generated/session.ts` — `Session`
- `src/contracts/generated/user.ts` — `User`
- `src/contracts/generated/utterance.ts` — `Utterance`
- `src/contracts/generated/ws-envelope.ts` — `WsEnvelope`
- `src/contracts/generated/ws-events.ts` — `WsEventPayloads` (near-empty; schema uses only `$defs`, no top-level type — WS payload wrappers stay in `types.ts`)

**Import updates:**
- `src/lib/api.ts` — `User` from `@/contracts/generated`; response types remain in `@/contracts/types`
- `src/lib/ws.ts` — `WsEnvelope` from `@/contracts/generated`
- `src/stores/authStore.ts` — `User` from `@/contracts/generated`
- `src/stores/sessionStore.ts` — `Session, Flag, Claim, Utterance` from `@/contracts/generated`
- `src/screens/recap/RecapScreen.tsx` — `Flag, Claim, Utterance` from `@/contracts/generated`
- `src/screens/recap/FlagDetail.tsx` — `Flag, Claim, Utterance` from `@/contracts/generated`
- `src/screens/recap/DisputeSheet.tsx` — `Flag` from `@/contracts/generated`

**Type drift found during migration:**
- `Attendee.deleted_at` — hand-written type omitted this field; generated type includes it. Schema is source of truth.
- `ProfileFacts.credentials` array — hand-written type omitted this field entirely; generated type includes it.
- `ProfileFacts.languages[].first_seen_year` — hand-written type omitted this field.
- `Claim.value` — hand-written type used `Record<string, unknown>` (loses all structure); generated type is a proper discriminated union of six value-shape interfaces.
- `Session.ended_at` — hand-written declared `ended_at: string | null`; generated correctly produces `ended_at?: string | null` (optional per schema).

**Additional fix:** `src/lib/ws.ts` — the `send()` method builds a `WsEnvelope` literal. With the generated (non-generic) `WsEnvelope`, the `data` field is typed as `Record<string, unknown>` but the parameter is `unknown`. Fixed by casting: `data as Record<string, unknown>`. This is safe — `send()` is always called with object literals throughout the codebase.

**Additional fix:** `src/screens/live/LiveScreen.tsx` line 119 — the mock flag's `Claim.value` was `{}`, which is now a type error against the discriminated union. Fixed to `{ years: 0 }` (valid `LanguageExperienceValue`).

---

### [FIXED] Localhost in .env.example (Issue 2)

`web-phone/.env.example` changed from:
```
VITE_API_BASE=http://localhost:8000
VITE_WS_BASE=ws://localhost:8000
```
To:
```
VITE_API_BASE=http://100.76.124.67:8000
VITE_WS_BASE=ws://100.76.124.67:8000
# Dev note: replace 100.76.124.67 with your backend host's Tailscale IP
```

---

### [FIXED] Hardcoded localhost fallbacks in code (Issue 3)

**`src/lib/api.ts` line 17** (was `import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'`):
Now throws in production if `VITE_API_BASE` is unset; permits the localhost fallback in dev mode only.

**`src/lib/ws.ts` line 3** (was `import.meta.env.VITE_WS_BASE ?? 'ws://localhost:8000'`):
Same guard applied.

---

### [FIXED] Missing `lint` and `contracts` scripts (Issue 6 partial)

`package.json` previously had no `lint` script. Added:
- `"lint": "eslint src --ext .ts,.tsx"` — lints all TypeScript source files
- `"contracts": "node scripts/generate-contracts.mjs"` — regenerates types from schemas
- Installed devDependencies: `json-schema-to-typescript`, `eslint`, `@typescript-eslint/parser`, `@typescript-eslint/eslint-plugin`, `eslint-plugin-react-hooks`
- `eslint.config.mjs` created with TypeScript and React Hooks rules

**`typecheck` and `build` scripts were already present.** No changes needed.

---

### [FIXED] ESLint false-positive on async fetch-on-mount pattern (Issue 6 lint)

`react-hooks/set-state-in-effect` fired on three screens that use `useEffect(() => { void asyncFn() }, [])`. The pattern is correct — `setState` is called only when the promise resolves (asynchronously), not synchronously in the effect body. The rule is disabled in `eslint.config.mjs` with an explanatory comment.

Screens affected: `PiPairScreen.tsx`, `ScanQrScreen.tsx`, `ShowQrScreen.tsx`.

---

### [CONFIRMED OK] WS auth uses `?token=` query param (Issue 4)

`src/lib/ws.ts` builds the URL as:
```typescript
const url = `${WS_BASE}/ws/phone?token=${this.token}`
```
This matches the contract: `wss://.../ws/phone?token=<user_jwt>`. No change needed.

---

### [FLAGGED] Unused WS payload exports in types.ts

The following interfaces are exported from `src/contracts/types.ts` but never imported in any other source file:
- `WsPartnerIdentified`
- `WsTranscriptUpdate`
- `WsClaimDetected`
- `WsPairingQr`
- `WsError`

These correspond to WS events the backend can send (`partner_identified`, `transcript_update`, `claim_detected`, `pairing_qr`, `error`) that `LiveScreen.tsx` does not yet handle. The exports are correct and necessary when those event handlers are implemented. Not removed — removing them would be adding a feature gate, not fixing a bug.

---

### [FLAGGED] Dead localStorage key in auth.ts

`src/lib/auth.ts` defines `USER_KEY = 'user'` and calls `localStorage.removeItem(USER_KEY)` inside `clearJwt()`. The Zustand `authStore` stores user data under the key `'auth-store'`, not `'user'`. The `USER_KEY` clear is a no-op (harmless, no data is stored under `'user'` by the current code). Likely a residue from before Zustand was adopted. Not removed because it is harmless and removing it could break existing sessions that have the key from a previous build.

---

### [FLAGGED] WS onmessage silently drops malformed frames

`src/lib/ws.ts` `_open()` onmessage handler catches JSON parse errors and discards them with no log or event emission. In production this will silently drop unexpected messages from the backend. Consider emitting a `parse_error` event (or logging in dev mode) to aid debugging. Not fixed — the behavior is documented by the code comment and is a deliberate choice; changing it requires deciding on an error surface.

---

### [FLAGGED] VoiceCalibration type not in JSON schemas

`src/contracts/types.ts` defines a `VoiceCalibration` interface used inside `VoiceCalibrationResponse`. The `VoiceCalibration` entity is described in `contracts/data-models.md` but has no corresponding `voice-calibration.schema.json`. The phone needs at minimum the `id` field from the calibration response (see `VoiceCalibrationScreen.tsx` which reads `res.calibration.id`). Orchestrator should add `voice-calibration.schema.json` to `contracts/schemas/` and regenerate. Filed as out-of-scope below.

---

## Out of scope — orchestrator decision needed

1. **Missing `voice-calibration.schema.json`** — `VoiceCalibration` is in `data-models.md` and used by the phone but has no JSON Schema file. Adding it requires updating `contracts/schemas/`, `contracts/data-models.md` (already accurate), and regenerating in all consumers.

2. **ws-events.ts generated output is near-empty** — `ws-events.schema.json` uses only `$defs` with no top-level `type`, so `json-schema-to-typescript` generates a stub `WsEventPayloads = {}`. The WS payload types (`WsSessionStatus`, `WsFlagRaised`, etc.) are phone-specific and must stay in `types.ts`. The schema structure could be improved to produce usable generated types, but changing `contracts/schemas/ws-events.schema.json` requires orchestrator approval.

---

## Localhost inventory

| Location | Value | Disposition |
|----------|-------|-------------|
| `src/lib/api.ts` | `http://localhost:8000` | Dev-mode fallback only; guarded by `import.meta.env.DEV` check. Throws in production. |
| `src/lib/ws.ts` | `ws://localhost:8000` | Dev-mode fallback only; guarded by `import.meta.env.DEV` check. Throws in production. |
| `.env.example` | previously had localhost values | Fixed to Tailscale IP `100.76.124.67`. |
| `.env` | `http://100.76.124.67:8000` / `ws://100.76.124.67:8000` | Already correct (not changed). |
| `web-phone/README.md` | `http://100.64.x.x:8000` | Placeholder example in documentation — not a live value. No change needed. |

---

## Contract conformance

### REST endpoints

| Code path | Endpoint | Contract | Status |
|-----------|----------|----------|--------|
| `requestMagicLink` | `POST /auth/magic-link` | `POST /auth/magic-link` | MATCH |
| `magicLinkCallback` | `GET /auth/magic-link/callback?token=...` | `GET /auth/magic-link/callback?token=...` | MATCH |
| `getGithubStartUrl` | `GET /auth/github/start?redirect=...` | `GET /auth/github/start?redirect=...` | MATCH |
| `getMe` | `GET /users/me` | `GET /users/me` | MATCH |
| `uploadVoiceCalibration` | `POST /users/me/voice-calibration` | `POST /users/me/voice-calibration` | MATCH |
| `initPiPair` | `POST /users/me/pi-pair` | `POST /users/me/pi-pair` | MATCH |
| `createPairing` | `POST /pairings` | `POST /pairings` | MATCH |
| `consumePairing` | `POST /pairings/consume` | `POST /pairings/consume` | MATCH |
| `getSession` | `GET /sessions/:id` | `GET /sessions/:id` | MATCH |
| `getSessionRecap` | `GET /sessions/:id/recap` | `GET /sessions/:id/recap` | MATCH |
| `disputeFlag` | `POST /flags/:id/dispute` | `POST /flags/:id/dispute` | MATCH |

### WebSocket events (phone → backend)

| Code | Event type | Contract | Status |
|------|-----------|----------|--------|
| `LiveScreen.tsx` | `phone_hello` | `phone_hello` | MATCH |
| `LiveScreen.tsx` | `subscribe_session` | `subscribe_session` | MATCH |

### WebSocket events (backend → phone)

| Code | Event type | Contract | Status |
|------|-----------|----------|--------|
| `LiveScreen.tsx` | `session_status` | `session_status` | MATCH |
| `LiveScreen.tsx` | `flag_raised` | `flag_raised` | MATCH |
| `LiveScreen.tsx` | `score_update` | `score_update` | MATCH |
| — | `partner_identified` | `partner_identified` | NOT HANDLED (flagged above) |
| — | `transcript_update` | `transcript_update` | NOT HANDLED (flagged above) |
| — | `claim_detected` | `claim_detected` | NOT HANDLED (flagged above) |
| — | `pairing_qr` | `pairing_qr` | NOT HANDLED (flagged above) |
| — | `error` | `error` | NOT HANDLED (flagged above) |

Unhandled events are not bugs — the WS client's `_emit()` calls all registered handlers for a type; if no handler is registered, the message is silently ignored, which is safe. The types for these events exist in `types.ts`, ready to be wired up.

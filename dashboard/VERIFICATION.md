# Dashboard Verification

## 2026-05-02 — .env.example created

Command: `cat dashboard/.env.example`
Output:
```
# Base URL of the FastAPI backend (Tailscale IP of the backend host)
NEXT_PUBLIC_API_BASE=http://100.76.124.67:8000

# Public URL of this dashboard (used for OAuth redirect URIs and link generation)
DASHBOARD_BASE_URL=http://100.76.124.67:3001
```
Result: PASS

---

## 2026-05-02 — api.ts localhost fallback documented

Command: `grep -A5 'NEXT_PUBLIC_API_BASE must be set' dashboard/src/lib/api.ts`
Output:
```
// NEXT_PUBLIC_API_BASE must be set at deploy time to point to the backend host.
// In local development (`npm run dev`) it falls back to http://localhost:8000.
// In production, omitting it means all API calls will silently target localhost —
// set NEXT_PUBLIC_API_BASE=http://100.76.124.67:8000 (or your Tailscale IP) in .env.local.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
```
Result: PASS

---

## 2026-05-02 — Dashboard README env examples use Tailscale IPs

Command: `grep '100.76.124.67' dashboard/README.md`
Output:
```
| `NEXT_PUBLIC_API_BASE` | yes | `http://100.76.124.67:8000` |
| `DASHBOARD_BASE_URL` | yes | `http://100.76.124.67:3001` |
```
Result: PASS

---

## 2026-05-02 — npm run build (full production build)

Command: `cd dashboard && npm run build 2>&1 | tail -20`
Output:
```
Route (app)                                 Size  First Load JS
┌ ○ /                                      127 B         102 kB
├ ○ /_not-found                            991 B         103 kB
├ ƒ /api/messages                          127 B         102 kB
├ ○ /events                              5.19 kB         107 kB
├ ƒ /events/[eventId]                    5.61 kB         108 kB
├ ƒ /events/[eventId]/live                5.1 kB         107 kB
└ ○ /sign-in                             1.67 kB         104 kB
+ First Load JS shared by all             102 kB

○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand
```
Result: PASS

Note: A warning about multiple lockfiles (`/Users/adityachoudhuri/package-lock.json` and the dashboard's own lockfile) appears but does not affect the build. This is a workspace root inference issue unrelated to this review scope.

---

## 2026-05-02 — Generated types tracked in git (flagged issue)

Command: `git ls-files dashboard/src/contracts/generated/ | wc -l`
Output: `12`

Confirmed: 12 generated TypeScript files are tracked in git. This is flagged in REVIEW.md — not fixed, as deletion would break the build. Requires orchestrator decision on gitignore strategy.
Result: FLAGGED (no action taken — documented)

---

# Tester-agent independent verification — 2026-05-02

All items below were re-verified cold by the tester agent reading source files and running commands directly. No application code was modified.

---

## CHECK 11 — Dashboard build

Command: `cd dashboard && npm run build 2>&1 | tail -20`
Output:
```
Route (app)                                 Size  First Load JS
┌ ○ /                                      127 B         102 kB
├ ○ /_not-found                            991 B         103 kB
├ ƒ /api/messages                          127 B         102 kB
├ ○ /events                              5.19 kB         107 kB
├ ƒ /events/[eventId]                    5.61 kB         108 kB
├ ƒ /events/[eventId]/live                5.1 kB         107 kB
└ ○ /sign-in                             1.67 kB         104 kB
+ First Load JS shared by all             102 kB

○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand
```
Exit code: 0. Build completes without errors.
Result: PASS

---

## CHECK 12 — dashboard/.env.example exists and is correct

File read: `dashboard/.env.example`

Full contents:
```
# Base URL of the FastAPI backend (Tailscale IP of the backend host)
NEXT_PUBLIC_API_BASE=http://100.76.124.67:8000

# Public URL of this dashboard (used for OAuth redirect URIs and link generation)
DASHBOARD_BASE_URL=http://100.76.124.67:3001
```

- `NEXT_PUBLIC_API_BASE=http://100.76.124.67:8000` — PRESENT and correct. PASS.
- `DASHBOARD_BASE_URL=http://100.76.124.67:3001` — PRESENT and correct. PASS.

Result: PASS

---

## CHECK 13 — Dashboard README Tailscale IPs

File read: `dashboard/README.md` — "Local environment" table (lines 91-95).

```
| `NEXT_PUBLIC_API_BASE` | yes | `http://100.76.124.67:8000` |
| `DASHBOARD_BASE_URL`   | yes | `http://100.76.124.67:3001` |
```

Both env var examples show Tailscale IPs. No `localhost` in the env var example table.
Result: PASS

---

## CHECK 14 — Dashboard api.ts fallback comment

File read: `dashboard/src/lib/api.ts` lines 148-152.

```typescript
// NEXT_PUBLIC_API_BASE must be set at deploy time to point to the backend host.
// In local development (`npm run dev`) it falls back to http://localhost:8000.
// In production, omitting it means all API calls will silently target localhost —
// set NEXT_PUBLIC_API_BASE=http://100.76.124.67:8000 (or your Tailscale IP) in .env.local.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
```

- Explanatory comment block is PRESENT. Explicitly states dev-only intent and warns about production misconfiguration. PASS.
- Fallback string is still `"http://localhost:8000"` (needed for dev). PASS.

Result: PASS

---

## Summary — all [FIXED] items

| # | REVIEW.md claim | Result |
|---|---|---|
| 1 | Backend import smoke test | PASS |
| 2 | pytest — 5 tests pass (including previously-failing async test) | PASS |
| 3 | CORS configurable via `CORS_ORIGINS` env var | PASS |
| 4 | WS routes use `?token=` query param, no path-param variants | PASS |
| 5 | `partner_identified` (not `subject_identified`) in all 3 send calls | PASS |
| 6 | `/debug/config` returns 404 when `fixture_mode=False` | PASS |
| 7 | `backend/.env.example` present with all required keys | PASS |
| 8 | `sim_pi.py` default URL uses Tailscale IP + query-param token | PASS |
| 9 | `verify_e2e.py` default base-url uses Tailscale IP | PASS |
| 10 | Structured logging at WS connect and per-message in both handlers | PASS |
| 11 | No stray `localhost`/`127.0.0.1` outside `config.py` | PASS |
| 12 | REST contract spot-check — all 6 routes match | PASS |
| 13 | Dashboard build exits 0 | PASS |
| 14 | `dashboard/.env.example` present with correct Tailscale IPs | PASS |
| 15 | `dashboard/README.md` env examples show Tailscale IPs | PASS |
| 16 | `dashboard/src/lib/api.ts` fallback has dev-only comment | PASS |

No FAILs. All [FIXED] items in both REVIEW.md files verified.

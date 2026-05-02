# REST API

Base URL (dev): `http://localhost:8000`
Base URL (prod): `https://api.larpchekr.app`

All requests/responses are JSON unless noted. All times ISO-8601 UTC.

## Auth

Two posture types:

- **User JWT** — `Authorization: Bearer <jwt>`. Issued via magic link.
- **Organizer JWT** — same, but `role: organizer` in the token.
- **Pi pairing token** — short-lived token issued at QR-pair time; used as WS query param only. No REST endpoints accept it.

Errors are uniform:

```json
{ "error": { "code": "string_enum", "message": "human readable", "details": { ... } } }
```

HTTP status codes are conventional; the body always has `error.code` for machine handling.

## Auth endpoints

### `POST /auth/magic-link`
Request a magic-link email.

```json
// req
{ "email": "alice@example.com" }
// res 202
{ "ok": true }
```

### `GET /auth/magic-link/callback?token=...`
Browser/app deep link. Returns a JWT.

```json
// res 200
{ "user": User, "jwt": "eyJ..." }
```

### `GET /auth/github/start?redirect=...`
Returns a GitHub OAuth URL. Used during onboarding step 2 (profile linking, **not** auth).

### `GET /auth/github/callback?code=...&state=...`
Backend exchanges the code, stores `github_login` on the user.

```json
// res 200
{ "user": User }
```

## User endpoints

### `GET /users/me`
Returns the authenticated user.

### `POST /users/me/voice-calibration`
Multipart upload of a 10–15s WAV. Backend extracts the embedding.

```http
POST /users/me/voice-calibration
Content-Type: multipart/form-data
fields: audio (file, audio/wav)
```

```json
// res 201
{ "calibration": VoiceCalibration }
```

### `POST /users/me/pi-pair`
Initiates Pi pairing. The phone shows the returned QR; the Pi scans it and POSTs to `/pi/claim`.

```json
// req
{}
// res 201
{ "pair_token": "...", "expires_at": "..." }
```

### `POST /pi/claim`
Pi-side endpoint. Pi has scanned the QR and claims the pairing.

```json
// req
{ "pair_token": "...", "device_id": "rpi-001", "firmware_version": "0.1.0" }
// res 201
{ "pi_token": "...", "user_id": "..." }   // pi_token used for WS auth
```

## Pairing (partner identification, not Pi pairing)

### `POST /pairings`
Authenticated user generates a QR token to show their partner.

```json
// res 201
{ "token": "...", "expires_at": "...", "qr_url": "https://..." }
```

### `POST /pairings/consume`
Authenticated user (the partner) scans the QR.

```json
// req
{ "token": "..." }
// res 201
{ "session_id": "..." }   // backend creates a session linking the two users
```

## Session endpoints

### `POST /sessions`
Manually create a session. Normally done implicitly via `/pairings/consume`. Used for solo demos.

```json
// req
{ "event_id": "..." }
// res 201
{ "session": Session }
```

### `GET /sessions/:id`
Authenticated. Returns the session if the user is `self_user_id` or an organizer of the event.

```json
// res 200
{ "session": Session }
```

### `GET /sessions/:id/recap`
Full recap data. Used by the recap screen.

```json
// res 200
{
  "session": Session,
  "partner": Attendee?,
  "utterances": Utterance[],
  "claims": Claim[],
  "flags": Flag[],
  "score": 0.42
}
```

### `POST /flags/:id/dispute`
User disputes a flag from the recap screen.

```json
// req
{ "reason": "I actually have done some Rust, just not on this account" }
// res 200
{ "flag": Flag }
```

## Organizer endpoints

All require `role: organizer` and the user to own the event.

### `POST /events`
```json
// req
{ "name": "...", "starts_at": "...", "ends_at": "...", "consent_jurisdiction": "us-ca", "retention_days": 30 }
// res 201
{ "event": Event }
```

### `GET /events/:id`
Returns the event with attendee count.

### `POST /events/:id/attendees/import`
CSV upload. Triggers async profile-link enrichment (fetches photos, headlines).

```http
POST /events/:id/attendees/import
Content-Type: multipart/form-data
fields: csv (file, text/csv)
```

CSV columns (header required, order flexible): `full_name,email,linkedin_url,github_login,resume_url`.

```json
// res 202
{ "import_job_id": "...", "estimated_seconds": 30 }
```

### `GET /events/:id/attendees/import/:job_id`
Poll the import job.

```json
// res 200
{ "status": "running" | "succeeded" | "failed", "rows_total": 120, "rows_done": 80, "errors": [...] }
```

### `GET /events/:id/attendees`
Paginated.

```
GET /events/:id/attendees?limit=50&cursor=...
```

```json
// res 200
{ "attendees": Attendee[], "next_cursor": "..." }
```

### `POST /events/:id/attendees`
Create one attendee manually.

### `PATCH /events/:id/attendees/:attendee_id`
Edit one attendee.

### `DELETE /events/:id/attendees/:attendee_id`
Soft-delete (sets `deleted_at`). Hard-delete is out of v1.

### `GET /events/:id/attendees/export`
Returns CSV with all enriched fields.

```http
GET /events/:id/attendees/export
Response: text/csv
```

## Health

### `GET /healthz`
Returns 200 OK if the server can reach MongoDB. No auth.

```json
{ "ok": true, "mongo": "ok", "version": "0.1.0" }
```

## Open questions

- Rate limits per endpoint? Hard-coded 60 rpm per user is fine for v1.
- Pagination — cursor vs. offset? Cursor (opaque, backend defines). Don't bother with offset for v1.
- Do we need a `POST /sessions/:id/end` for clean teardown? Probably yes; add when phone needs it.

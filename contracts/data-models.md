# Data models

Canonical entity definitions. JSON Schemas in [`schemas/`](./schemas/) are the source of truth; this doc is the human-readable companion.

## Entity map

```
User ─┬─ owns ─→ Pairing(QR token)
      ├─ links ─→ Profile (github | linkedin | resume)
      ├─ joins ─→ Attendee ─→ Event
      └─ has ──→ VoiceCalibration

Session ─┬─ self_user → User
         ├─ partner_attendee → Attendee  (resolved post-pairing)
         ├─ has many ─→ Utterance
         ├─ has many ─→ Claim
         └─ has many ─→ Flag

Claim ─→ Utterance
Flag  ─→ Claim, Profile
```

## User

The L4RPCH3KR account. One per attendee with the app installed.

| Field | Type | Notes |
|-------|------|-------|
| `id` | ulid | server-generated |
| `email` | string | unique, used for magic link |
| `display_name` | string | shown in recap, dashboard |
| `created_at` | datetime | |
| `voice_calibration_id` | ulid? | nullable until onboarding step 3 |
| `github_login` | string? | nullable until onboarding step 2 |

## Event

A hackathon. Created by an organizer.

| Field | Type | Notes |
|-------|------|-------|
| `id` | ulid | |
| `name` | string | "AGI House Spring 2026" etc. |
| `starts_at` / `ends_at` | datetime | |
| `consent_jurisdiction` | string | e.g. `us-ca`. Drives the consent posture. |
| `retention_days` | int | how long to keep transcripts |
| `created_by_user_id` | ulid | organizer |

## Attendee

A `User` joined to an `Event`, plus the organizer-curated profile data. This is what the backend compares claims against.

| Field | Type | Notes |
|-------|------|-------|
| `id` | ulid | |
| `event_id` | ulid | FK |
| `user_id` | ulid? | nullable — attendees imported via CSV before they sign up |
| `full_name` | string | from CSV |
| `email` | string | from CSV; used to link when user signs up |
| `headline` | string? | from CSV / LinkedIn enrichment |
| `linkedin_url` | string? | |
| `github_login` | string? | |
| `resume_url` | string? | uploaded by organizer or attendee |
| `photo_url` | string? | enriched from LinkedIn / GitHub |
| `consented_to_recording` | bool | set true on partner-side opt-in flow |
| `imported_at` | datetime | |

## Profile

Cached, normalized view of an attendee's verifiable signal. One row per source per attendee. Refreshed lazily on first use.

| Field | Type | Notes |
|-------|------|-------|
| `id` | ulid | |
| `attendee_id` | ulid | FK |
| `source` | enum | `github | linkedin | resume` |
| `fetched_at` | datetime | |
| `data` | jsonb | source-specific normalized blob |
| `facts` | jsonb | extracted, comparable facts (see "Profile facts" below) |

### Profile facts

A flattened, comparable representation. Examples:

```json
{
  "languages": [{"name": "rust", "evidence": "github", "confidence": 0.6, "loc": 12000}],
  "experience": [{"company": "google", "title": "swe", "start": "2022-01", "end": "2024-06"}],
  "education": [{"school": "mit", "degree": "bs", "field": "cs", "end": "2022"}],
  "projects": [{"name": "foo", "stars": 42, "url": "..."}]
}
```

The full set is defined in `schemas/profile-facts.schema.json`.

## Session

One conversation between the user and a partner. Starts when the Pi connects and a partner is identified; ends on disconnect or explicit stop.

| Field | Type | Notes |
|-------|------|-------|
| `id` | ulid | |
| `event_id` | ulid | |
| `self_user_id` | ulid | the wearer |
| `partner_attendee_id` | ulid? | resolved during/after pairing |
| `partner_consent_status` | enum | `pending | granted | denied` |
| `started_at` | datetime | |
| `ended_at` | datetime? | |
| `pi_device_id` | string | hardware id of paired Pi |

## Utterance

One contiguous block of speech, attributed to `self` or `partner`.

| Field | Type | Notes |
|-------|------|-------|
| `id` | ulid | |
| `session_id` | ulid | |
| `speaker` | enum | `self | partner | unknown` |
| `speaker_confidence` | float | [0,1], cosine similarity vs. calibrated embedding |
| `started_at` / `ended_at` | datetime | |
| `text` | string | ASR output |
| `audio_url` | string? | short signed URL, expires post-event |

## Claim

A factual assertion extracted from a partner utterance.

| Field | Type | Notes |
|-------|------|-------|
| `id` | ulid | |
| `utterance_id` | ulid | |
| `kind` | enum | see "Claim kinds" |
| `subject` | string | e.g. "rust", "google", "stanford" |
| `predicate` | string | e.g. "experience_years", "worked_at", "graduated_from" |
| `value` | jsonb | shape varies by `kind` |
| `hedge` | enum | `none | weak | strong` |
| `extraction_confidence` | float | [0,1], from the LLM |
| `text_span` | string | the snippet of utterance.text |

### Claim kinds

- `language_experience` — "I've been writing X for N years"
- `employment` — "I worked at X"
- `education` — "I went to X / studied Y"
- `project` — "I built X" / "I shipped X"
- `credential` — "I have a PhD in X" / "I'm a Y at Z"
- `quantitative` — "I have N stars on X" / "my repo gets N downloads"

Each kind's `value` shape is in `schemas/claim.schema.json`.

## Flag

A discrepancy between a `Claim` and the partner's `Profile`.

| Field | Type | Notes |
|-------|------|-------|
| `id` | ulid | |
| `claim_id` | ulid | |
| `profile_id` | ulid | which profile contradicted |
| `severity` | enum | `low | medium | high` — drives haptic intensity |
| `score_delta` | float | added to session larp score |
| `verified_text` | string | human-readable rebuttal: "GitHub shows 0 Rust commits" |
| `confidence` | float | [0,1] |
| `created_at` | datetime | |
| `disputed` | bool | user pressed dispute in recap |
| `dispute_reason` | string? | |

### Severity rubric

- `low`: hedged claim with mild contradiction. No haptic. Quiet card.
- `medium`: unhedged claim, clear contradiction in one source. Single haptic pulse. Standard card.
- `high`: unhedged numeric/credential claim, contradicted by primary source. Triple pulse. Bold card.

## Larp score

Per-session float in [0, 1], computed as a logistic on summed `score_delta` weighted by recency. Formula in `backend/app/scoring.py` (TBD). Not currently exposed publicly — only in the recap.

## VoiceCalibration

| Field | Type | Notes |
|-------|------|-------|
| `id` | ulid | |
| `user_id` | ulid | |
| `embedding` | float[192] | ECAPA-TDNN vector stored in MongoDB |
| `sample_audio_url` | string | for re-calibration |
| `created_at` | datetime | |

## Pairing

QR-code handshake for partner identification.

| Field | Type | Notes |
|-------|------|-------|
| `token` | string | short-lived, single-use |
| `issuer_user_id` | ulid | who generated the QR |
| `expires_at` | datetime | 60s default |
| `consumed_by_user_id` | ulid? | who scanned it |
| `consumed_at` | datetime? | |

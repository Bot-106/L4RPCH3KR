# Contracts

The seams between Pi, backend, phone, and dashboard. **This is the most important folder in the repo** — every cross-subsystem assumption lives here. If you change a schema, you change every consumer in the same PR.

## Files

- [`data-models.md`](./data-models.md) — entity definitions (User, Event, Attendee, Session, Utterance, Claim, Flag, Profile). Read first.
- [`websocket-events.md`](./websocket-events.md) — every WS message: direction, trigger, payload, ordering guarantees.
- [`rest-api.md`](./rest-api.md) — every REST endpoint: auth, request, response, error shapes.
- [`schemas/*.schema.json`](./schemas/) — machine-readable JSON Schemas. Source of truth.

## Source of truth

The JSON Schema files in `schemas/` are the source of truth. Markdown docs describe and exemplify; if they disagree with a schema, the schema wins.

## Generated types

Each subsystem generates its own typed bindings from the schemas. No subsystem hand-writes types for these entities.

| Subsystem | Tool | Output path |
|-----------|------|-------------|
| Backend (Python) | `datamodel-code-generator` | `backend/app/contracts/generated/` |
| Web-phone (TS) | `json-schema-to-typescript` | `web-phone/src/contracts/generated/` |
| Dashboard (TS) | `json-schema-to-typescript` | `dashboard/src/contracts/generated/` |
| Pi (Python) | `datamodel-code-generator` (subset only — only WS events it sends/receives) | `pi/larpchekr/contracts/generated/` |

Each subsystem's `Makefile` or `package.json` should expose a `make contracts` / `npm run contracts` task that regenerates from `../contracts/schemas/`. **Don't hand-edit generated files.** For demo reliability they are committed to git (not gitignored), but they must be regenerated any time a schema changes. Run `npm run contracts` / `make contracts` in every consumer after any schema edit.

## Versioning

For the hackathon, schemas are unversioned and breaking changes ripple immediately. Post-hackathon, add a `version` field to each top-level schema and a deprecation policy. Don't bother with this in v1.

## How to change a contract

1. Edit the schema file.
2. Update the matching markdown doc.
3. Regenerate types in every consumer.
4. Open one PR with all changes. CI fails if generated types are out of date.

## Conventions

- All timestamps: ISO-8601 UTC (`2026-05-01T12:34:56.789Z`).
- All IDs: ULID-style strings (`01HX...`). Generated server-side; clients never mint IDs except for client-only correlation.
- All audio: 16 kHz mono PCM s16le over WS (binary frames). 250 ms chunks.
- All images (Pi → backend): JPEG, max 640×480, max 1 frame / 10s.
- WS messages (non-binary): JSON, one message per frame, with required `type` and `id` fields. Schema in `schemas/ws-envelope.schema.json`.
- Enums are `lower_snake_case` strings.
- Money / scores: floats in [0, 1] for confidence; integers for counts. Never localized strings on the wire.

## Open questions

- Should we use protobuf for audio frames to save bandwidth on hackathon wifi? Probably not — JSON envelope + binary audio frames is fine for a 4-day build. Revisit if we hit bandwidth issues.
- Do we need request signing on the Pi WS connection (HMAC with paired token), or is a JWT bearer enough? Decide after pairing flow stabilizes.

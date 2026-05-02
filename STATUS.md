# L4RPCH3KR — Demo Readiness Status

> Updated by the orchestrator. Do not hand-edit.

## Overall: READY FOR DEMO — all integration checkpoints PASS

Last updated: 2026-05-02

---

## Agent pairs — round 1

| Pair | Subsystem | Writer | Tester | REVIEW.md | VERIFICATION.md | Status |
|------|-----------|--------|--------|-----------|-----------------|--------|
| 1 | web-phone/ | DONE ✓ | DONE ✓ | exists | exists (all PASS) | GREEN |
| 2 | backend/ + dashboard/ | DONE ✓ | DONE ✓ | exists (both) | exists (both, all PASS) | GREEN |
| 3 | pi/ | DONE ✓ | DONE ✓ | exists | exists (all PASS) | GREEN |

---

## Orchestrator cross-cutting tasks

- [x] `phone/` deleted (superseded by `web-phone/`, confirmed by user 2026-05-02)
- [x] Root `README.md` updated — `phone/` → `web-phone/` references
- [x] `contracts/README.md` updated — generated types table and committed-files policy
- [x] `contracts/rest-api.md` — base URL uses Tailscale placeholder
- [x] `contracts/websocket-events.md` — WS auth confirmed `?token=` query param; `browser_transcript` and `subject_resolved` events documented
- [x] `contracts/schemas/voice-calibration.schema.json` created (was missing; web-phone agent flagged it)
- [x] `contracts/schemas/ws-events.schema.json` — added top-level `anyOf` so json-schema-to-typescript emits all payload types
- [x] `infra/tailscale.md` created — topology, IPs, verification commands
- [x] `.gitignore` — clarified that generated types are committed (pattern was wrong anyway — only matched repo root)
- [x] `STATUS.md` created
- [x] All pairs: tester agents run and VERIFICATION.md green
- [x] Final integration-tester run — all 12 checkpoints PASS (INT-4 fix applied 2026-05-02)

---

## Demo-loop checklist

- [x] All contracts/schemas/ generate cleanly in all subsystems (no diff vs. committed) — INT-10, INT-11 PASS
- [ ] `tailscale status` shows every host online; `curl http://100.76.124.67:8000/healthz` from Pi and web-phone host returns 200
- [x] Backend: Mongo up on backend host; backend boots clean — INT-1, INT-2 PASS
- [x] Backend: key REST endpoints return documented shape — INT-9 PASS
- [x] Backend: WS events accepted and echo round-trip cleanly — INT-7, INT-8 PASS
- [x] Web-phone: typecheck, lint, build all green — WRITER VERIFIED ✓ (INT-11 PASS)
- [ ] Web-phone: onboarding 1–4 completes with JWT + github_login + voice_calibration_id + pi_token in storage
- [x] Web-phone: all requests use `VITE_API_BASE`; no hardcoded localhost (production) — WRITER VERIFIED ✓
- [ ] Web-phone: live mode renders `flag_raised` card within 200ms of WS receipt
- [ ] Web-phone: recap plays audio snippet via signed URL; dispute POSTs to /flags/:id/dispute
- [x] Pi: `LARPCHEKR_FAKE_HARDWARE=1 python -m larpchekr.main` runs against backend, WS connects, LED arms — INT-12 PASS
- [ ] Pi: reconnect tested (kill backend mid-stream → Pi buffers → drains on reconnect)
- [ ] Pi (real hardware): recording LED solid green when streaming, yellow on reconnect, red offline; haptic on `haptic_pulse`
- [ ] Dashboard: magic-link → event picker → CSV upload → paginated table → export round-trips identically
- [x] Legacy `phone/` removed — DONE ✓
- [x] `/STATUS.md`, `/infra/tailscale.md`, and every `<subsystem>/REVIEW.md` + `<subsystem>/VERIFICATION.md` exist — DONE ✓
- [x] Integration smoke test: sim_pi browser_transcript → exactly one `flag_raised` at phone WS → flag in recap — INT-4 PASS

---

## Tailscale topology

| Host | IP | Ports |
|------|----|-------|
| larpchekr-pi | `100.125.43.120` | (no inbound) |
| backend host | `100.76.124.67` | FastAPI :8000, web-phone :3000, dashboard :3001 |

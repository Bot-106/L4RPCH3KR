# infra/

Deploy and local-dev infrastructure. No application code lives here.

## Files

- `docker-compose.dev.yml` — Postgres (with pgvector) + Redis for local dev. Both subsystems Engineer B owns connect to these.

## Production deploy (TBD)

For the demo we'll likely deploy:

- Backend → Fly.io or Railway, single region, single instance.
- Dashboard → Vercel (Next.js native target).
- Postgres → Railway / Supabase managed.
- Redis → Railway / Upstash.

Engineer B picks one stack and writes the deploy notes here on day 1. Don't bikeshed.

## Open questions

- Do we need a separate worker process for `arq` jobs, or is in-process enough? In-process is fine for v1; split later if CSV imports starve the API.
- TLS termination: Fly handles it. If self-hosted, Caddy in front.

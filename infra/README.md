# infra/

Local development and deployment notes for L4RPCH3KR.

## Files

- `docker-compose.dev.yml` - MongoDB for local development. The backend stores events, attendees, sessions, utterances, claims, flags, profile summaries, and scores here.

## Local Dev

Start MongoDB before running the backend:

```bash
docker compose -f infra/docker-compose.dev.yml up -d mongo
```

Then run the backend, dashboard, and phone app from their own folders.

## Demo Deployment Shape

- Backend: single FastAPI instance.
- Dashboard: Next.js deployment.
- Database: managed MongoDB or local MongoDB for demo testing.

The project was built for EurekaHacks 2026 in under 24 hours, so deployment notes should stay lightweight and demo-focused unless this becomes a production project.

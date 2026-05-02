# dashboard/ - Organizer Dashboard

Next.js organizer dashboard for L4RPCH3KR, built for the EurekaHacks 2026 demo. It gives organizers a control panel for events, attendees, profile enrichment, flags, CSV workflows, and the global Larperboard.

## Scope

- Organizer sign-in against the backend auth flow.
- Event picker and event creation.
- CSV attendee import.
- Manual attendee creation.
- Attendee table with editable profile fields.
- Per-attendee profile summary/comparison fetch.
- Event flags view.
- Global Larperboard with optional event filtering.
- Event-scoped leaderboard route redirecting to the global Larperboard filter.
- CSV export.
- Arcade-styled UI based on the L4RPCH3KR design system.

## Tech Stack

- Next.js 15 App Router
- TypeScript
- React
- Custom CSS arcade visual system in `src/styles/globals.css`
- Backend REST client in `src/lib/api.ts`

## Running Locally

```bash
cd dashboard
npm install
cp .env.example .env.local
npm run dev
```

Default local URL: `http://localhost:3000`

Backend URL comes from `NEXT_PUBLIC_API_BASE` in `.env.local`.

## Useful Commands

```bash
npm run typecheck
npm run build
```

## Key Routes

| Route | Purpose |
|-------|---------|
| `/sign-in` | Organizer login |
| `/events` | Event picker and event creation |
| `/events/[eventId]` | Attendee table, create-user flow, import/export, profile comparison |
| `/events/[eventId]/flags` | Event flags |
| `/leaderboard` | Global Larperboard with optional event filter |

## Backend Dependency

The dashboard talks to the FastAPI backend over REST. Start `backend/` first and set `NEXT_PUBLIC_API_BASE` to the backend origin.

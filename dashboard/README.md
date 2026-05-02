# dashboard/ — Organizer dashboard

Owner: **Engineer B** (same as backend).

Web app for hackathon organizers. Imports an attendee CSV with profile-link enrichment, lets organizers CRUD attendees, and exports the enriched CSV back. Not attendee-facing.

## Scope

In:
- Sign in (organizer JWT, magic-link).
- Event picker (organizer can own multiple events).
- CSV upload + enrichment progress UI.
- Paginated attendee table with inline edit.
- Per-attendee detail panel (photo, headline, linked profiles, consent state).
- CSV export.
- Empty / loading / error states for everything above.

Out (v1):
- Live conversation viewing (organizers don't watch live sessions).
- Public larp leaderboard.
- Per-attendee stats / aggregates.
- Branding / white-label.

## Tech stack

- **Next.js 15** (App Router) + **TypeScript**
- **Tailwind CSS** + **shadcn/ui** for components
- **TanStack Query** for server state
- **TanStack Table** for the attendee table
- **react-hook-form** + **zod** for forms (zod schemas generated where possible from `contracts/schemas/`)
- **next-auth** (or just a thin custom magic-link page hitting backend) — start custom, swap to next-auth only if needed
- Deploys to Vercel

## File layout

```
dashboard/
├── README.md
├── package.json
├── tsconfig.json
├── next.config.mjs
├── tailwind.config.ts
├── postcss.config.js
├── .env.example
├── public/
│   └── icons/                 ← from design/assets
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx           ← redirect to /events
│   │   ├── (auth)/
│   │   │   └── sign-in/page.tsx
│   │   ├── events/
│   │   │   ├── page.tsx       ← event picker
│   │   │   └── [eventId]/
│   │   │       ├── layout.tsx
│   │   │       ├── page.tsx   ← attendee table
│   │   │       ├── import/page.tsx
│   │   │       └── attendees/[attendeeId]/page.tsx
│   │   └── api/                ← thin proxy to backend if needed
│   ├── components/
│   │   ├── ui/                 ← shadcn primitives
│   │   ├── attendee-table.tsx
│   │   ├── csv-uploader.tsx
│   │   ├── import-progress.tsx
│   │   └── attendee-form.tsx
│   ├── lib/
│   │   ├── api.ts              ← typed REST client
│   │   ├── auth.ts
│   │   └── tokens.ts           ← reads design/tokens/tokens.json
│   ├── contracts/
│   │   └── generated/          ← from /contracts (gitignored)
│   └── styles/
│       └── globals.css
└── tests/
    └── e2e/
```

## External interfaces

### Consumes
- Backend REST per `contracts/rest-api.md`. Specifically the `/events/*`, `/auth/*`, `/users/me` surfaces. **No WS** — dashboard is request/response only.
- Design tokens at `../design/tokens/tokens.json`.
- Icon SVGs at `../design/assets/icons/*.svg`.

### Exposes
- HTTPS web app. URL TBD by Engineer B.

### Local environment
Reads from `dashboard/.env.local`:

| Var | Required | Example |
|-----|----------|---------|
| `NEXT_PUBLIC_API_BASE` | yes | `http://localhost:8000` |
| `DASHBOARD_BASE_URL` | yes | `http://localhost:3000` |

## Local setup

```bash
cd dashboard
npm install
npm run contracts          # regen TS types from /contracts/schemas
cp .env.example .env.local
npm run dev                # http://localhost:3000
```

Backend must be running at `NEXT_PUBLIC_API_BASE`.

## MVP checklist

- [ ] Magic-link sign-in for organizer accounts.
- [ ] Event picker (no event = empty state with "create event" CTA).
- [ ] CSV upload with file-type validation, ≤5 MB.
- [ ] Import progress poller, error list rendering.
- [ ] Attendee table: paginated, sortable by name/email/imported_at.
- [ ] Inline edit `headline`, `linkedin_url`, `github_login`, `resume_url`.
- [ ] Soft-delete with undo toast.
- [ ] CSV export (returns the same shape as import + enriched fields).
- [ ] Loading + empty + error states for every screen.
- [ ] Renders correctly with placeholder design tokens; reskins cleanly when designer ships final tokens.

## Non-goals

- Mobile responsiveness below 1024px (organizer uses a laptop).
- Dark mode (until designer ships it).
- Real-time updates of the attendee table.
- Bulk actions beyond import/export.

## Open questions

- Auth: do organizers and attendees share `User` with a `role`, or are they separate? Backend's call. Default: shared `User`, role flag.
- Profile-link enrichment: which fields actually fetch? GitHub: avatar, bio, repos. LinkedIn: just store the URL — no scraping. Resume: extract structured fields with the LLM (out of v1 if too slow).
- Do we surface flags / sessions to organizers in v1? **No.** Read-only later.

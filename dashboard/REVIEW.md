# Dashboard Review

## Issues found

### [FIXED] Category: Missing `.env.example`

**File:** `dashboard/.env.example` (created)

**What was wrong:** The file was referenced in `dashboard/README.md` setup instructions (`cp .env.example .env.local`) but did not exist.

**What was changed:** Created `dashboard/.env.example` with both required env vars using Tailscale IPs:
- `NEXT_PUBLIC_API_BASE=http://100.76.124.67:8000`
- `DASHBOARD_BASE_URL=http://100.76.124.67:3001`


### [FIXED] Category: `api.ts` localhost fallback in production

**File:** `dashboard/src/lib/api.ts` line 148 (before fix)

**What was wrong:** `const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"` silently used localhost when `NEXT_PUBLIC_API_BASE` was unset in any environment, including production. There was no indication in the code that the fallback is wrong for production, and no documentation.

**What was changed:** Added an explanatory comment block making clear that:
- `NEXT_PUBLIC_API_BASE` must be set at deploy time to the correct Tailscale IP.
- `localhost` is only appropriate for `npm run dev` local development.
- Omitting the var in production means API calls silently target localhost.

Note: A throw-on-missing approach was explored but rejected because Next.js evaluates `NEXT_PUBLIC_*` variables at build time during static prerendering. Throwing during module initialization causes the build itself to fail when the env var is absent from the CI/build environment. The comment-based approach keeps the build unconditionally passing while providing a clear signal to developers.


### [FIXED] Category: Dashboard README uses localhost in env var examples

**File:** `dashboard/README.md`

**What was wrong:** The "Local environment" table showed `http://localhost:8000` for `NEXT_PUBLIC_API_BASE` and `http://localhost:3000` for `DASHBOARD_BASE_URL`. These are the wrong values for the deployed Tailscale topology.

**What was changed:** Updated examples to use Tailscale IPs:
- `NEXT_PUBLIC_API_BASE`: `http://100.76.124.67:8000`
- `DASHBOARD_BASE_URL`: `http://100.76.124.67:3001`


### [FLAGGED] Category: Committed generated types inconsistent with gitignore

**Files:** `dashboard/src/contracts/generated/*.ts` (12 files)

**What is wrong:** The root `.gitignore` contains the pattern `contracts/generated/`, which is intended to exclude generated type files from version control. However, `dashboard/src/contracts/generated/` is tracked in git (confirmed via `git ls-files dashboard/src/contracts/generated/`).

The gitignore pattern `contracts/generated/` matches paths of the form `contracts/generated/` anywhere in the tree. Whether it also matches `dashboard/src/contracts/generated/` depends on git's glob rules — apparently it does not in this repo's configuration, so the files are tracked.

**Why NOT deleted:** The generated files are required for the dashboard to build (`npm run build` passes with them present). Deleting them without first running `npm run contracts` would break the build.

**Resolution needed (orchestrator):** Either:
- Add a more specific gitignore pattern such as `**/contracts/generated/` to exclude the files consistently, and add a CI step that regenerates them and fails if the output differs (ensuring generated files stay in sync without being committed), OR
- Keep the files committed (current state) and remove the `contracts/generated/` gitignore entry or narrow it to only match the root path.

The gitignore contracts/README.md says "Don't hand-edit generated files. They're gitignored." — the current state contradicts this documentation.


---

## Out of scope — orchestrator decision needed

None beyond the generated-types gitignore issue documented above.


---

## Localhost inventory

| Location | Value | Disposition |
|----------|-------|-------------|
| `dashboard/src/lib/api.ts` `API_BASE` fallback | `"http://localhost:8000"` | **Intentional for dev** — documented with comment. Production must set `NEXT_PUBLIC_API_BASE`. |
| `dashboard/README.md` env example (before fix) | `http://localhost:8000`, `http://localhost:3000` | **Fixed** — updated to Tailscale IPs. |

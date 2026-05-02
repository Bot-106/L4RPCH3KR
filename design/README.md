# design/ — For the designer

Owner: **Designer** (Figma).

This folder is the design ↔ code contract. Treat it like an API: stable shapes, predictable update flow, breaking changes are a coordinated event.

## What lives here

```
design/
├── README.md                    ← you are here
├── tokens/
│   ├── tokens.example.json      ← placeholder tokens engineering uses until you ship
│   └── tokens.json              ← (you create this) the real tokens, exported from Figma
└── assets/
    ├── icons/                   ← *.svg, naming below
    ├── illustrations/           ← *.svg or *.png @2x/@3x
    └── lotties/                 ← *.json (Lottie) for animated states
```

The Figma file itself lives in Figma — not in git. The export pipeline writes JSON / SVG / PNG into this folder.

## What you deliver for MVP

### Locked-scope screens
Engineering needs the exact specs for these. Pixel layout, every state.

| # | Screen | Owner side |
|---|--------|------------|
| 1 | Onboarding 1 — Sign in (email entry + magic-link sent state) | phone |
| 2 | Onboarding 2 — Connect GitHub (button + connected state) | phone |
| 3 | Onboarding 3 — Voice calibration (idle, recording, success, retry) | phone |
| 4 | Onboarding 4 — Pi pair (QR display, pairing, paired) | phone |
| 5 | Live mode — Status pill states (armed, recording, disconnected) | phone |
| 6 | Live mode — Flag card (low / medium / high severity, dismissed) | phone |
| 7 | Recap — Conversation summary + flag list | phone |
| 8 | Recap — Flag detail with dispute sheet | phone |
| 9 | Dashboard — Attendee table (loaded, empty, loading, error) | dashboard |
| 10 | Dashboard — CSV upload (idle, uploading, importing, errors) | dashboard |

### Designer's-call screens
Engineering implements to a generic spec; you reskin once Figma is ready. No need to block on these.

- Sign-in for organizers (assume same shape as attendee sign-in unless you say otherwise).
- Event picker dropdown.
- Toast / notification component.
- Loading skeletons.

### What engineering does without final designs
Each engineering README has the same line: "if Figma isn't ready, build to placeholder tokens and a generic layout — designer reskins later." So nobody is blocked. Ship what you can in any order.

## Design tokens (the contract)

Tokens are the shared vocabulary. Engineering imports `tokens/tokens.json` and uses it everywhere — Tailwind theme on the dashboard, RN theme on the phone. **Don't hard-code colors / sizes / radii in code.** Don't hand-tweak tokens in code either; they get overwritten on the next export.

### Format

We use the [W3C Design Tokens Community Group](https://design-tokens.github.io/community-group/format/) format, which is also what the **Tokens Studio** plugin exports. One file: `design/tokens/tokens.json`.

A placeholder `tokens.example.json` is in the repo. Engineering uses it as the schema reference; replace it with `tokens.json` when ready.

### Required token groups

- `color/` — semantic color names. **Do not** export Figma layer colors directly; export semantic names.
  - `color/bg/canvas`, `color/bg/surface`, `color/bg/raised`
  - `color/text/primary`, `color/text/secondary`, `color/text/muted`, `color/text/inverse`
  - `color/border/default`, `color/border/strong`
  - `color/accent/default`, `color/accent/strong`
  - `color/severity/low`, `color/severity/medium`, `color/severity/high`
  - `color/status/recording`, `color/status/armed`, `color/status/offline`
- `font/family/sans`, `font/family/mono`
- `font/size/{xs,sm,md,lg,xl,2xl,3xl}` (numeric, in pt for RN — engineering converts to rem for web)
- `font/weight/{regular,medium,semibold,bold}`
- `font/lineHeight/{tight,normal,relaxed}`
- `spacing/{0,1,2,3,4,6,8,12,16,24}` (numeric, base 4pt grid)
- `radius/{sm,md,lg,full}`
- `shadow/{sm,md,lg}` (RN-friendly: `{ x, y, blur, color, opacity }`)
- `motion/duration/{fast,normal,slow}` (ms)
- `motion/easing/{standard,emphasized}` (cubic-bezier coords)

If you add categories, fine — just document them here. Don't rename existing ones without coordination.

### How to update tokens

1. In Figma, edit the token in Tokens Studio.
2. Export to JSON (Tokens Studio → "Export" → JSON, single file).
3. Save as `design/tokens/tokens.json`.
4. Open a PR that **only** changes `tokens.json`. Engineering will rebuild on the next dev cycle. If a token is removed, engineering needs a heads-up — drop a note in the PR.

## Asset pipeline

### Icons
- Format: SVG, no fill (we tint via CSS / props).
- Naming: `kebab-case`, descriptive, no size suffix. Good: `microphone.svg`. Bad: `icon-mic-24.svg`.
- viewBox: `0 0 24 24` for all icons. Stroke-based icons preferred (matches `lucide-react`'s shape).
- Location: `design/assets/icons/`.
- Engineering imports them as React components (web: SVGR; RN: `react-native-svg-transformer`).

### Illustrations
- Format: SVG if the illustration is vector-clean; otherwise PNG @2x and @3x.
- Naming: `kebab-case-illustration.svg` or `kebab-case-illustration@2x.png`.
- Location: `design/assets/illustrations/`.

### Lottie animations
- Format: Lottie JSON exported via Bodymovin / LottieFiles.
- Naming: `kebab-case.json`.
- Location: `design/assets/lotties/`.

## Figma → code handoff convention

- One Figma file, organized by page: `Cover / Foundations / Onboarding / Live Mode / Recap / Dashboard`.
- Each screen has a frame named exactly the README's locked-scope label (e.g. "Onboarding 3 — Voice calibration").
- Each frame has all states stacked or in named variants (Figma component variants preferred). State names match what's listed in the README ("idle", "recording", "success", "retry").
- For each component used cross-screen (button, pill, card), publish it as a Figma component and document its props in a `Components` page.
- When something's done, mark the frame `✅ DONE` in the layer name (not in a label inside the frame; the layer name is what we look at).

## What engineering needs from you, in priority order

1. **Day 0:** publish initial `tokens.json` even if values are first-pass guesses. This unblocks every engineer immediately.
2. **Day 1:** onboarding screens 1–4 locked.
3. **Day 2:** live mode (status pill + flag card).
4. **Day 3:** recap + dashboard table.

If you slip on anything except #1, engineering will ship to placeholder layouts — no panic.

## Open questions

- Are we doing dark mode at MVP? Default: **no**. Keep tokens light-only and add `color/bg/canvas-dark` etc. in v2.
- Brand: do we have a logo / wordmark? If yes, export `assets/illustrations/logo.svg` and `assets/illustrations/wordmark.svg`. If no, engineering uses a placeholder.
- The Pi enclosure: do you want creative input on the 3D-printed shell, or is that purely Engineer A's? Coordinate directly with them.

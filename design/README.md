# design/ - Visual System

Design references and UI direction for the L4RPCH3KR EurekaHacks 2026 demo.

## What Lives Here

- Design tokens and token examples.
- Arcade/operational visual references.
- Exported assets used by the dashboard and phone app.
- Notes for keeping UI surfaces visually consistent across the hackathon demo.

## Current Direction

The shipped dashboard uses a loud arcade-style interface: hard borders, high-contrast surfaces, pixel-inspired typography, severity colors, and score-forward layouts. The goal is to make flags and Larperboard ranking feel immediate and game-like while still being readable for organizers.

## Token Contract

Design tokens should stay stable across app surfaces. If `tokens/tokens.json` changes, update the consuming UI in the same pass when possible.

Useful token groups:

- `color/bg/*`
- `color/text/*`
- `color/border/*`
- `color/accent/*`
- `color/severity/*`
- `font/*`
- `spacing/*`
- `radius/*`
- `motion/*`

## Asset Guidelines

- Use SVG for icons and clean vector illustrations.
- Use kebab-case file names.
- Keep reusable assets under `design/assets/`.
- Avoid baking color into icons when CSS tinting is possible.

## Implemented Surfaces

- Organizer sign-in.
- Event picker.
- Event detail and attendee table.
- Create-user flow.
- Import/export controls.
- Flags view.
- Larperboard.

## Notes

This folder documents the hackathon visual system rather than a finished production design system. Keep future additions pragmatic and aligned with the existing arcade UI.

# 0018: Clear roster button, no roster picker, proctor log layout

**Date:** 2026-10-02 · **Decided by:** PM (scope, button), Claude (layout, motion)

## Decisions
- **No student dropdown in the proctor Bathroom log.** Typing the ID and seeing the name line is enough. The wireframe's "or pick from roster" is dropped.
- **Clear roster is built.** Roster tab -> **Clear roster...** (admin only, visible when a roster exists) -> type DELETE -> `POST /api/staff/roster/clear` (protocol 0.12.0). It deletes every row in Postgres and memory in one transaction (`replace_roster([])`), and is idempotent. This is deliberately a **hard delete**, an exception to "deleting is always soft" (design principle 0): the data is names and contacts of minors, a soft copy would keep it, and re-importing the CSV restores it. Bathroom records keep their IDs but lose names (names are resolved when lists are built). The SQL in `setup-contestdojo.md` stays as the fallback.
- **ContestDojo Sync stays the next step and the only Phase 1 blocker**, waiting on the maintainers (ADR 0017). Nothing else is open in Phase 1 besides the C1/C6/C11 gate evidence and the Oct 5 demo.
- **Docs sweep:** the PM reported that everything is deployed, CI is green, `/healthz` and `/readyz` are fine and all screens were checked in browsers; `STATUS.md`, `phase-0.md`, `phase-1.md` and `development-plan.md` now say so, crediting the PM's report as the evidence.

## Proctor log layout and motion (`/animate`, `/apple-design`, `design-principles.md`)
- Marking someone out happens a few times per test, so motion is short and quiet: a new row eases in (the existing `row-in`: opacity + a 6 px rise, 220 ms, ease-out); a returned row fades to 50 % (250 ms); a late row (10+ min) warms to amber with a 3 px accent bar. Only `opacity`, `transform` and colors move; reduced motion is handled by the global rule. No keyframes on anything that can be hit twice quickly (transitions retarget; keyframes only run on mount).
- The press feedback already in `button:active` (scale .97, 100 ms) is kept; the ID field and Mark out are 56 px tall for a thumb, the ID is mono 20 px.
- One flat keyed list (out now, a small "Back" divider, then returned rows), so a student who returns keeps the same DOM row instead of being rebuilt and re-animated. A header pill says "N out" / "Nobody out"; the empty state says what will appear.
- Known gap: when someone returns, the row jumps to the Back group while fading (no slide). Add a FLIP slide only if the dress rehearsal shows it confuses people.

# 2026-10-02: Claude: slice 15, Clear roster, proctor log layout, docs sweep, chaos runbook

**Ticket / phase item:** Phase 1 wrap-up (PM requests in chat).
**Directories touched:** `server/`, `web/`, `contracts/`, `docs/`
**PR / commits:** not committed; delivered as a git patch.

## Done
- **Clear roster:** `POST /api/staff/roster/clear` (admin only, idempotent, `replace_roster([])`), route added to `schema_app.py`, protocol 0.12.0 (changelog, §7.8, endpoint table), `openapi.json` and `api-types.ts` regenerated. Web: `Clear roster…` button on the Roster tab with a type-DELETE sheet (`ClearSheet` in `Roster.tsx`). Test `test_roster_clear`.
- **Proctor Bathroom log layout and motion** (`BathroomLog.tsx`, `styles.css`): header with "N out" pill, 56 px mono ID field, card rows with a big "N min" and the clock time, amber accent for 10+ min, "Back" divider, one flat keyed list so returning a student doesn't remount the row. Details and motion rules: ADR 0018.
- **Docs sweep:** `STATUS.md` rewritten, `phase-1.md` ticked (`[?]` -> `[x]`, "not tried in a browser" removed, blocker section, slice log 14-15), `phase-0.md`, `development-plan.md` progress paragraph, `README.md`, `setup-contestdojo.md`, `CLAUDE.md` (stale "protocol v0.1.0"), ADR 0017 addendum, ADR 0018, new `chaos-phase1.md`.

## Verified how
- `uv run pytest -q`: 117 passed, 8 skipped (no Postgres here). `ruff check` and `ruff format --check` clean. `npm run gen && npm run build` pass.
- **Not run by me:** the new layout and Clear roster button in a browser, and the real-Postgres test set. Browser/deploy/CI/health status in the docs comes from the PM's report on 2026-10-02, not from my own checks.

## Not done / blocked
- ContestDojo Sync vs the real API (waiting on the maintainers). Only open Phase 1 item.
- Chaos C1/C6/C11 and the Oct 5 demo: steps in `docs/chaos-phase1.md`, results blank.
- No FLIP slide when a returned row changes group (noted in ADR 0018).

## Next steps for whoever picks this up
- Deploy (no new migration this slice), try Clear roster on a throwaway roster and look at the proctor log on a phone.
- Work through ContestDojo Sync with the maintainers, then run C1/C6/C11 and record them.

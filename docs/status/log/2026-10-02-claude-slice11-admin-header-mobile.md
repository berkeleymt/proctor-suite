# 2026-10-02: Claude (chat session): Slice 11, mobile admin header + contract/test repair

**Phase item:** Phase 1 follow-up (PM request: responsive admin header)
**Directories touched:** `web/src/{components/ui.tsx,screens/Admin.tsx,screens/Clarifications.tsx,styles.css,api-types.ts}`, `contracts/openapi.json`, `server/tests/test_clarifications.py`, `docs/`
**PR / commits:** none; uncommitted (patch). Started from `6bb3c76`.

## Done
- One shared `AdminBar` for Timers and Clarifications (replaces two copies of the header markup). Wide screens look the same as before. At <= 1040 px: ☰ (turns into ✕), the current tab on the left, the connection light at the far right. The menu opens as an overlay under the bar (no layout shift) with tabs, summary, "Show deleted", Add room (Timers) and Log out stacked in the desktop order; the light is hidden while it is open. It closes on Esc, on a click outside, and after pressing any button or link inside it.
- Repair from slice 10 (the sandbox then had no network): regenerated `contracts/openapi.json` and `web/src/api-types.ts`; removed one stale assertion in `test_edit_keeps_old_wording_visible` (`{body, room_id}` is a per-room edit since 0.8.0).

## Verified how
- `uv run pytest`: 98 passed against a throwaway Postgres (migrations 0001-0006 ran); `ruff check` and `ruff format --check` clean. `npm run build` (tsc + vite) passes.
- NOT verified: the header in a browser at any width (no browser available here; the download host is blocked). Breakpoint 1040 px is an estimate from the Timers summary line length.

## Decisions made
- Breakpoint 1040 px, so tablets in portrait and small laptop windows also get the menu; one `Dot` is rendered twice (desktop-only inside the menu row, mobile-only outside it) so the light can leave the open menu without moving on desktop.

## Next steps
See `STATUS.md` ("Next actions").

# 2026-10-02: Claude: slice 13, bathroom log (proctor side)

**Ticket / phase item:** Phase 1, wireframe "Bathroom log (proctor)" (New). Next gap after slices 1-12.
**Directories touched:** `server/`, `web/`, `contracts/`, `docs/`
**PR / commits:** not committed (files patched in the working tree)

## Done
- Server: migration `0008_bathroom_visits`; `db.py` load/insert/mark-back; `Store.bathroom_out` / `bathroom_return` (commit to Postgres, then memory, then notify); `RoomSnapshot` gains `students_out`, `bathroom_out`, `bathroom_back`; two endpoints in `api.py`. Protocol 0.10.0, `openapi.json` regenerated, `api-types.ts` regenerated.
- Web: `components/BathroomLog.tsx` on the proctor panel (ID field, Mark out, Currently out with live time and a 10-minute highlight, Returned, Recently returned). Admin Timers: **Out** column and "N students out" in the summary.
- Docs: protocol §7.7, endpoint rows, constants, changelog; ADR 0015.

## Verified how
- `cd server && uv run pytest -q`: 103 passed, 6 skipped (no Postgres).
- With Postgres 16 (`TEST_DATABASE_URL=postgresql://t:t@localhost:5432/t`): 110 passed, including `test_bathroom_log_survives_restart_and_goes_with_its_room` (migration 0008, restart, Empty removes rows).
- `uv run ruff check . && uv run ruff format --check .` clean. `cd web && npm run gen && npm run build` passes.
- New tests (`tests/test_bathroom.py`): out/back, retry with the same id is a no-op, double-out 409, id reuse 409, return twice is a no-op, other room's proctor 403, anonymous 401, admin allowed, validation 422, staff list has counts not names, 50-out cap, 20-returned cap.

## Not done / blocked
- **Not tried in a browser** (none in the sandbox). The layout, the live "out for" time, the late highlight, and the admin Out column are build-checked only.
- Admin Bathroom tab, Roster (both "Later"), the display "Log" drawer, and the projector mirror are not built. Chat is still waiting on a PM decision.
- Offline marking (phase 2): times are server time for now (ADR 0015).

## Decisions made
- ADR 0015.

## Next steps for whoever picks this up
- Deploy (migration 0008) and try the panel on a phone: mark out, kill the wifi, retry, mark back, watch the admin Out column on a second device.
- Small wireframe gaps still open: the **Preview display** button in Clarifications, and the display "Log" drawer.
- Then the Oct 5 gate: deploy, run the demo with 3+ devices, chaos C1/C6/C11.

# 2026-10-01: Claude (chat session): Slice 2, admin "Add room" end to end

**Phase item:** Phase 1, admin "add room" (wireframe: Admin · Timers, Create room/timer)
**Directories touched:** `server/app/{api,store}.py`, `server/app/protocol/{models,constants}.py`, `server/tests/test_api.py`, `contracts/openapi.json`, `docs/`, `web/src/screens/Admin.tsx`, `web/src/styles.css`, `.gitignore`
**Commits:** none; files left uncommitted for a human to review and push. Starting commit `37138e8`.

## Done
- Server: `POST /api/staff/rooms` (admin only, CSRF header, 201/401/403/409/422). Contract bumped to 0.2.0 (ADR 0005, protocol.md §10 + §14).
- Web: "Add room" button in the admin bar opens a sheet (room, duration default 180). New row slides in (opacity/transform, 240 ms, reduced-motion safe). Esc and scrim click close it. Error text from the server is shown inline.
- New rooms appear in the login dropdown immediately (same store).
- `.gitignore` had `.DS_Store` and `web/dist/` glued on one line, so `web/dist` was being tracked. Fixed the file; the tracked copy still needs `git rm -r --cached web/dist` (Caddy builds the web itself).

## Verified how
- `uv run pytest`: 72 passed (new: create room, auth, duplicate, invalid name, default duration, appears in login list, new room can log in). ruff check + format clean.
- `npm run gen`, `npm run build`: succeed.
- NOT verified: UI in a real browser (still `[?]` for all web screens); docker build; prod.

## Not done
- Doc URL, change duration, reset, hide, rename (wireframe items, later slices). No persistence yet.

## Next steps
1. Push, deploy (README), try login -> proctor -> admin -> Add room on two devices. Fix breakage before anything else.
2. Slice 3: Postgres + first Alembic migration run by `deploy.sh` (rooms must survive restarts).
3. Then SSE + heartbeat; then "Change duration" (admin) on the same pattern as this slice.

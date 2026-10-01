# 2026-10-01: Claude (chat session): Slice 3, admin "Edit…" and Duration column

**Phase item:** Phase 1, admin timers (wireframe: Admin · Timers, row action Edit…, Duration column, test label)
**Directories touched:** `server/app/{api,store}.py`, `server/app/protocol/{models,constants,schema_app}.py`, `server/tests/test_api.py`, `contracts/openapi.json`, `docs/`, `web/src/{api.ts,api-types.ts,screens/Admin.tsx,styles.css}`
**Commits:** none; uncommitted for a human to review and push. Started from `95ee807` (pulled; slice 2 is already on main).

## Done
- Server: `PATCH /api/staff/rooms/{room_id}` (admin/PM, CSRF header; 401/403/404/409/422), optional `test_name` on room create. Protocol 0.3.0 (ADR 0006, protocol.md section 10 and 14).
- Web: Duration column; "Edit…" per row opens the same sheet used by Add room (duration, test label); duration is disabled with a hint once started; Add room gained the test label field.

## Verified how
- `uv run pytest`: 73 passed (new: edit before start, version bump, 422 on bad duration, 404, 409 after start, label still editable after start). ruff clean.
- `npm run gen`, `npm run build`: succeed.
- NOT verified: UI in a real browser (still `[?]` for all web screens), docker build, prod.

## Not done
Doc URL, Reset, bulk actions, confirm dialogs, Hide, persistence, SSE.

## Next steps
1. Push, deploy, and click through login, Add room, Edit, start on two devices. Fix breakage first.
2. Then either Postgres (rooms survive restarts) or the bulk select + "Start selected / +5 min selected" bar (web only, one command per room).

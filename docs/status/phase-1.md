# Phase 1: Prototype

Source: `development-plan.md` §6. **Window:** Wed Sep 30 – **Mon Oct 5**. **Gate:** Oct 5 demo with 3+ phones/laptops on one room plus the staff dashboard, all in sync on AWS; chaos tests C1, C6, C11 pass.

Not in the prototype: offline outbox, Service Worker, clarifications, bathroom log, exports.

## Server (owner: Ian)
- [~] Postgres schema + first Alembic migration; `deploy.sh` runs it (invariant 10). Written and tested against local Postgres 16 (slice 4); not yet run in the compose stack or on prod
- [~] Seed tooling: rooms seeded once from `SEED_ROOMS` into an empty DB (slice 4). No event/test tables yet
- [x] In-memory state loaded at startup from Postgres (`app/store.py load`; test `test_state_survives_restart`, slice 4)
- [x] `GET /api/time` (slice 1; `server/app/api.py`, tested)
- [~] Auth: all endpoints + CSRF header done and tested (slice 1). Missing: rate limiting; sessions are in memory
- [~] `POST /api/commands`: roles, idempotency, 409 conflict done and tested. Commit-before-memory done in slice 4 (listeners are notified only after the commit and memory update; slice 6)
- [~] Commands run through `app/fold.py` (fixtures still pass); events are saved to Postgres (`commands` table) and replayed at startup. No separate `events`/`room_current` tables yet
- [x] `/snapshot?since_version`, `GET /api/staff/rooms`, `GET /api/rooms/{id}/stream`, `GET /api/staff/stream` (slice 1, slice 6; `app/stream.py`)
- [x] Tests (SSE part, slice 6): initial snapshot, per-room filtering, new rooms reach staff, heartbeat, unsubscribe, 401/404. Earlier: command idempotency, role matrix, SSE initial snapshot + heartbeat

## Frontend (owner: Forrest)
- [x] `web/` scaffold + generated types (`npm run gen`, checked in CI). Build passes locally
- [~] Clock sync + backoff in `web/src/{api,hooks}.ts`; `useLive` = SSE with our own backoff reconnect, 35 s dead-stream rule, polling only while the stream is down (slice 6). No TS fold yet (remaining time is computed from the snapshot). Not tried in a browser or through Caddy
- [?] Login + "Is this your room?" built (slice 1); not tried in a browser
- [?] Proctor control (slice 1, slice 5): Start / Pause / Resume, and Start, Open display window and Log out on one row, timer with A-/A+ zoom. Not tried in a browser
- [?] Display / projector screen (slice 5): light theme, timer auto-fits any screen size, A-/A+ zoom (remembered per device), controls fade after 4 s. No clarifications area or paragraph zoom yet (no clarifications feature). Not tried in a browser
- [~] Admin Timers (slices 1-5), wireframe items done: summary line, Add room (name, duration, test label), Edit (duration before start, test label), Duration and Test columns, per-row Allow start / Start / +5 min with confirm (Shift skips), column filters (room text, test, status, duration), bulk select of visible rows with Allow start / Start / +5 min / Edit duration and test label. Missing: end, Reset, Hide, doc URL, "Show hidden", students-out count. Not tried in a browser

## Deploy and demo
- [ ] Deployed to AWS via `deploy.sh`
- [ ] Oct 5 demo run; evidence recorded here (date, devices, outcome)
- [ ] Chaos C1, C6, C11 pass (Forrest decides if the gate is green)

## Decide before starting
- Protocol §13 open questions (non-blocking).

## Slice log
- Slice 6 (2026-10-01): SSE streams + heartbeat, `useLive` client with polling fallback, design-principles doc, ADR 0009, `log/2026-10-01-claude-slice6-sse.md`.
- Slice 5 (2026-10-01): bulk Allow start + bulk Edit, column filters, projector display with fit-to-screen timer and zoom, proctor single action row, docs sweep, ADR 0008, `log/2026-10-01-claude-slice5-display-filters.md`.
- Fix (2026-10-01, already pushed): compose `migrate` service so `docker compose up --build` works on an empty DB (ADR 0007).
- Slice 4 (2026-10-01): Postgres persistence, bulk select, ADR 0007, `log/2026-10-01-claude-slice4-postgres-bulk.md`.
- Slice 3 (2026-10-01): admin Edit (duration before start, test label), Duration column, protocol 0.3.0, ADR 0006, `log/2026-10-01-claude-slice3-edit-room.md`.
- Slice 2 (2026-10-01): admin Add room, protocol 0.2.0, ADR 0005, `log/2026-10-01-claude-slice2-add-room.md`.
- Slice 1 (2026-10-01): see `log/2026-10-01-claude-slice1.md` and ADR 0004.

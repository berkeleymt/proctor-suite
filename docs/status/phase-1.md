# Phase 1: Prototype

Source: `development-plan.md` §6. **Window:** Wed Sep 30 – **Mon Oct 5**. **Gate:** Oct 5 demo with 3+ phones/laptops on one room plus the staff dashboard, all in sync on AWS; chaos tests C1, C6, C11 pass.

Not in the prototype: offline outbox, Service Worker, clarifications, bathroom log, exports.

## Server (owner: Ian)
- [~] Postgres schema + first Alembic migration; `deploy.sh` runs it (invariant 10). Written and tested against local Postgres 16 (slice 4); not yet run in the compose stack or on prod
- [~] Seed tooling: rooms seeded once from `SEED_ROOMS` into an empty DB (slice 4). No event/test tables yet
- [x] In-memory state loaded at startup from Postgres (`app/store.py load`; test `test_state_survives_restart`, slice 4)
- [x] `GET /api/time` (slice 1; `server/app/api.py`, tested)
- [~] Auth: all endpoints + CSRF header done and tested (slice 1). Missing: rate limiting; sessions are in memory
- [~] `POST /api/commands`: roles, idempotency, 409 conflict done and tested. Commit-before-memory done in slice 4 (broadcast waits for SSE)
- [~] Commands run through `app/fold.py` (fixtures still pass); events are in memory only
- [~] `/snapshot?since_version` and `GET /api/staff/rooms` done (slice 1). SSE streams not started
- [ ] Tests: command idempotency, role matrix, SSE initial snapshot + heartbeat

## Frontend (owner: Forrest)
- [x] `web/` scaffold + generated types (`npm run gen`, checked in CI). Build passes locally
- [~] Clock sync + backoff + polling in `web/src/{api,hooks}.ts`. No SSE client; no TS fold yet (remaining time is computed from the snapshot)
- [?] Login + "Is this your room?" built; not tried in a browser
- [?] Built; not tried in a browser
- [?] Built; not tried in a browser
- [~] Built: list, allow start, start on behalf, +5 min. Add room done in slice 2 (`log/2026-10-01-claude-slice2-add-room.md`). Edit (duration/test label) done in slice 3. Bulk select + confirm dialogs done in slice 4. Missing: end, reset. Not tried in a browser

## Deploy and demo
- [ ] Deployed to AWS via `deploy.sh`
- [ ] Oct 5 demo run; evidence recorded here (date, devices, outcome)
- [ ] Chaos C1, C6, C11 pass (Forrest decides if the gate is green)

## Decide before starting
- Protocol §13 open questions (non-blocking).

## Slice log
- Slice 4 (2026-10-01): Postgres persistence, bulk select, ADR 0007, `log/2026-10-01-claude-slice4-postgres-bulk.md`.
- Slice 3 (2026-10-01): admin Edit (duration before start, test label), Duration column, protocol 0.3.0, ADR 0006, `log/2026-10-01-claude-slice3-edit-room.md`.
- Slice 2 (2026-10-01): admin Add room, protocol 0.2.0, ADR 0005, `log/2026-10-01-claude-slice2-add-room.md`.
- Slice 1 (2026-10-01): see `log/2026-10-01-claude-slice1.md` and ADR 0004.

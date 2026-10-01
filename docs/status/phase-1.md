# Phase 1: Prototype

Source: `development-plan.md` §6. **Window:** Wed Sep 30 – **Mon Oct 5**. **Gate:** Oct 5 demo with 3+ phones/laptops on one room plus the staff dashboard, all in sync on AWS; chaos tests C1, C6, C11 pass.

Not in the prototype: offline outbox, Service Worker, clarifications, bathroom log, exports.

## Server (owner: Ian)
- [ ] Postgres schema + first Alembic migration; `deploy.sh` runs it (invariant 10)
- [ ] Seed tooling: one event, rooms, a test, one current session per room
- [ ] In-memory state loaded at startup from `room_current`
- [ ] `GET /api/time`
- [ ] Auth: `GET /api/auth/rooms`, room login (display + control), staff login, logout, `/api/me`, cookies, `X-Proctor-Client` check
- [ ] `POST /api/commands` for permit/start/pause/resume/end/adjust: roles per protocol §6.2, idempotent on `command_id`, commit-then-broadcast
- [ ] Event store uses the fold (`app/fold.py` or its successor) and passes all fixtures
- [ ] `GET /api/rooms/{id}/stream` (SSE + heartbeat), `/snapshot?since_version`, `GET /api/staff/rooms`, `/api/staff/stream`
- [ ] Tests: command idempotency, role matrix, SSE initial snapshot + heartbeat

## Frontend (owner: Forrest)
- [ ] `web/` scaffold (Vite + React + TS), generate types from `contracts/openapi.json`
- [ ] `sync-core` basics: clock sync, SSE client with backoff, fold in TS passing all fixtures
- [ ] Login screen (room dropdown + password) and "Is this your room?" confirmation
- [ ] Display screen (timer, connection indicator)
- [ ] Control screen (start / pause with confirm modal / resume)
- [ ] Bare staff dashboard (room list, grant permission, start on behalf, end, adjust)

## Deploy and demo
- [ ] Deployed to AWS via `deploy.sh`
- [ ] Oct 5 demo run; evidence recorded here (date, devices, outcome)
- [ ] Chaos C1, C6, C11 pass (Forrest decides if the gate is green)

## Decide before starting
- Protocol §13 open questions (non-blocking).

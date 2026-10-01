# 2026-10-01: Claude (chat session): Slice 1, "start a room's timer" end to end

**Ticket / phase item:** Phase 1 (server auth/commands/snapshot, web scaffold, login, display, control, bare admin)
**Directories touched:** `server/app/{api,store,main}.py`, `server/tests/test_api.py`, `web/` (new), `infra/{Caddyfile,caddy.Dockerfile,docker-compose.yml,.env.example}`, `.github/workflows/ci.yml`, `README.md`, `docs/`
**PR / commits:** none; files left uncommitted for a human to review and push. Starting commit `8efbb91`.

## Done
- Server: `GET /api/time`, `GET /api/auth/rooms`, room login, staff login, logout, `/api/me`, `GET /api/rooms/{id}/snapshot` (304 support), `GET /api/staff/rooms`, `POST /api/commands` (all six types, roles per protocol §6.2, idempotent on `command_id`, 409 on conflict, stale-session rejection). Uses the existing `fold.py`; no contract change (PROTOCOL_VERSION unchanged).
- Web (Vite + React + TS, types generated from `contracts/openapi.json`): login (dropdown, Admin pinned first, `?room=` and `?surface=display` links), "Is this your room?" gate, proctor panel (Start / Pause with confirm sheet / Resume, Open display window), display screen (timer, room + test label, connection dot), bare admin table (Allow start, Start on behalf, +5 min, status counts).
- Clock sync (lowest-RTT of 8), full-jitter backoff, one request in flight, 10 s timeout, command retry reusing the same `command_id`.
- Infra: Caddy now builds and serves `web/dist` and proxies `/api`, `/healthz`, `/readyz`. Compose passes the new env vars. CI got a `web` job (types up to date + build).

## Verified how
- `uv run ruff check .`, `ruff format --check .`, `uv run pytest`: 71 passed (4 new API tests: public endpoints, login + CSRF header, permit→start loop with idempotency and role checks, cross-room read blocked).
- `npm run gen` and `npm run build`: succeed.
- NOT verified: the UI in a real browser; `docker compose build` (no Docker in the sandbox); the shellcheck job; prod. Treat the web screens as `[?]`.

## Not done / blocked
- No persistence, SSE, offline (Service Worker/IndexedDB), TS fold, chaos tests. Wireframe features beyond timers/login are untouched.
- Prod needs `ROOM_PASSWORD` and `ADMIN_PASSWORD` added to `infra/.env` before the next deploy, or compose refuses to start.

## Decisions made
- ADR 0004 (slices, wireframe as scope ceiling, slice 1 shortcuts).

## Next steps for whoever picks this up
1. Push, deploy (README), and try the loop on a phone + laptop. Fix anything broken before adding more.
2. Slice 2: Postgres schema + first Alembic migration run by `deploy.sh`, commit-before-memory, load state at startup (closes invariant 5 gap).
3. Slice 3: SSE stream + heartbeat. Then Admin "Add room", then pause/adjust UI polish.

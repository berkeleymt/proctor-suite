# 2026-10-01: Claude (chat session): Slice 4, Postgres persistence + bulk select

**Phase item:** Phase 1 server (schema + Alembic, state loaded at startup, commit-before-memory) and wireframe Admin · Timers (bulk actions, confirmations)
**Directories touched:** `server/{app,alembic,tests,pyproject.toml,uv.lock,Dockerfile,alembic.ini}`, `infra/{deploy.sh,.env.example}`, `.github/workflows/ci.yml`, `web/src/{hooks.ts,screens/Admin.tsx,styles.css}`, `README.md`, `docs/`
**Commits:** none; uncommitted for a human to review and push. Started from `49adb21` (pulled).

## Done
- Migration `0001` (rooms, commands), `app/db.py`, async `Store` with commit-before-memory, lifespan load + seed-once, per-room locks, 503 on database errors. ADR 0007.
- `deploy.sh` runs Alembic before `up`; Dockerfile copies `alembic/`; CI server job has a Postgres 17.11 service and sets `TEST_DATABASE_URL`.
- Web: select column, "N selected" bar (Start selected, +5 min selected, Clear), confirmation sheet with Shift-skip, same for per-row +5 min.

## Verified how
- Local PostgreSQL 16 in the sandbox (prod is 17.11): `uv run pytest` with `TEST_DATABASE_URL`: 75 passed (new: state survives a restart incl. versions, test label, duration, idempotent replay of both normal and stale commands; a failed commit leaves memory untouched). Without the variable: 73 passed, 2 skipped. ruff clean.
- Manual: ran the real Alembic migration, created a room through the API, simulated a restart, the room was still listed; `/readyz` returned `ready`.
- `npm run build` passes.
- NOT verified: UI in a real browser (bulk select, confirm sheet, and every other web screen are still `[?]`), `docker compose build`, `dc run` migration in the real compose stack, shellcheck, prod. The CI Postgres service block has not run on GitHub.

## Not done
SSE, rate limiting, persistent sessions, pgdata backups, Reset, Hide, doc URL.

## Next steps
1. Push, deploy, and on the server check `docker compose logs app` shows no errors and `/readyz` says ready. Restart the app container and confirm rooms and running timers survive.
2. Try bulk Start on 3+ rooms from two devices.
3. Then SSE + heartbeat (replace polling), or Reset/Hide on the same pattern.

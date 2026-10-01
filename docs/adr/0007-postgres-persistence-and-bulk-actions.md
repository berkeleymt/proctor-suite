# 0007: Postgres persistence (rooms + commands) and bulk select

**Date:** 2026-10-01 · **Decided by:** PM (direction), Claude (details). No contract change: PROTOCOL_VERSION stays 0.3.0 (503 `unavailable` already exists in protocol 6.5).

## Decision
- **Two tables** (Alembic `0001`): `rooms` (settings + `version`) and `commands` (every accepted command, in order, with `is_event`, `outcome`, `reason`). `commands` is the event log and the idempotency record in one: events are the rows with `is_event`; rejected-as-stale commands are rows with `is_event = false`.
- **Commit before memory** (invariant 5): `Store.apply/create_room/update_room` compute the result without mutating, write to Postgres, then change memory. A failed write changes nothing and returns 503; the client retries with the same `command_id`. The insert uses `ON CONFLICT (command_id) DO NOTHING`, so a retry after an ambiguous failure is safe.
- **Load at startup** (FastAPI lifespan): memory is rebuilt from Postgres. If `DATABASE_URL` is set and the database is down, the app refuses to start. Empty database: seed rooms from `SEED_ROOMS` once. Room `version` is stored and restored, otherwise pollers holding a higher version would get 304 forever after a restart.
- **One lock per room** serializes commands in the single process (invariant 9); a global lock guards room creation.
- **Migrations** run by `deploy.sh` (`dc run --rm migrate`) after building the image and before `up`; never inside the app process (invariant 10). Forward-only, additive. Compose also has a one-shot `migrate` service the app waits for (`service_completed_successfully`), so a plain local `docker compose up --build` works on an empty database. The app still crashes at startup if tables are missing (by design).
- **No `DATABASE_URL`** = memory-only (unit tests, quick local runs). Real-Postgres tests run when `TEST_DATABASE_URL` is set; CI now has a Postgres service.
- **Sessions (logins) are still memory-only**: a restart signs everyone out. Seeding and `SEED_ROOMS` apply only to an empty database.
- **Bulk select** (web only, one command per room as protocol 12 says): checkbox column + select-all, "Start selected" (permit then start where needed; running or finished rooms are skipped) and "+5 min selected" (finished rooms skipped). At most 6 requests in flight. A confirmation sheet shows how many rooms; Shift-click skips it (wireframe). Per-row +5 min now asks for confirmation too (wireframe: "Reset and +5 ask for confirmation").

## Not done
SSE, rate limiting, persistent sessions, backups of `pgdata`, Reset, Hide, doc URL.

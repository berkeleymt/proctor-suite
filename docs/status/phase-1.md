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
- [?] Display / projector screen (slice 5): light theme, timer auto-fits any screen size, A-/A+ zoom (remembered per device), controls fade after 4 s. Slices 8-10: clarifications (quiet "Clarifications" heading, Auto size = 3 steps below the largest fit) under a top-pinned timer, Markdown + math, ¶−/Auto/¶+, edited ones crossed out, optional Google Doc iframe instead of the list. Not tried in a browser
- [?] Admin Timers (slices 1-7): summary line, Add room, Edit (name, duration before start, test label, doc link), filters (room, test, status, duration, pages open), per-row actions by timer state (Allow start, Start, Pause, Resume, Reset, +5 min, "more" menu with Edit and Delete), confirm dialogs (Shift skips), bulk Allow start / Start / +5 / Edit / Delete (type DELETE), "Show deleted" with Restore, Proctor/Display presence dots. Missing: End (protocol has it, wireframe doesn't show it), doc link display, "Show hidden" is called "Show deleted". Slice 10: deleted rooms also have Empty… (permanent). Not tried in a browser
- [?] Proctor panel timer states (slice 7): Start (locked until allowed), Pause, Resume, "Time's up"; hint line explains disabled buttons. Not tried in a browser

- [?] Admin Clarifications (slices 8-9): navbar tabs, composer with live Markdown/math preview, compact room picker (All rooms / All building / All test / Clear + searchable list), posted list with a summary and per-room Rooms popover, Edit (old text stays crossed out), Hide (asks first; Edit instead), Delete, per-room Hide/Delete. Server tests pass incl. real Postgres; not tried in a browser. Slice 10: header counts + light + Log out, live list without reload, Delete is soft with "Show deleted" (Restore, Empty…), per-room Edit (that room gets its own copy). Missing: Preview-display button. No Deletion tab (cancelled, ADR 0013)

## Deploy and demo
- [ ] Deployed to AWS via `deploy.sh`
- [ ] Oct 5 demo run; evidence recorded here (date, devices, outcome)
- [ ] Chaos C1, C6, C11 pass (Forrest decides if the gate is green)

## Decide before starting
- Protocol §13 open questions (non-blocking).

## Slice log
- Slice 10 (2026-10-02): auto size, heading, clarifications header, live admin list, soft delete + Restore + Empty (clarifications and rooms), per-room edit, Deletion tab cancelled; protocol 0.8.0, migration 0005, ADR 0013, `log/2026-10-02-claude-slice10-soft-delete-per-room-edit.md`.
- Slice 9 (2026-10-02): clarification edit, delete, per-room hide/delete, Markdown + KaTeX, projector layout and ¶ size, doc iframe, navbar tabs; protocol 0.7.0, migration 0004, ADR 0012, `log/2026-10-02-claude-slice9-clarification-edit-delete.md`.
- Slice 8 (2026-10-01): clarifications: post to all/some rooms, hide/unhide, projector list; protocol 0.6.0, migration 0003, ADR 0011, `log/2026-10-01-claude-slice8-clarifications.md`.
- Slice 7 (2026-10-01): timer states (admin Pause/Resume/Reset, proctor Time's up), rename/delete/restore/doc link, presence, shared Sheet/Menu/Dot, protocol 0.4.0, migration 0002, ADR 0010, `log/2026-10-01-claude-slice7-room-management.md`.
- Slice 6 (2026-10-01): SSE streams + heartbeat, `useLive` client with polling fallback, design-principles doc, ADR 0009, `log/2026-10-01-claude-slice6-sse.md`.
- Slice 5 (2026-10-01): bulk Allow start + bulk Edit, column filters, projector display with fit-to-screen timer and zoom, proctor single action row, docs sweep, ADR 0008, `log/2026-10-01-claude-slice5-display-filters.md`.
- Fix (2026-10-01, already pushed): compose `migrate` service so `docker compose up --build` works on an empty DB (ADR 0007).
- Slice 4 (2026-10-01): Postgres persistence, bulk select, ADR 0007, `log/2026-10-01-claude-slice4-postgres-bulk.md`.
- Slice 3 (2026-10-01): admin Edit (duration before start, test label), Duration column, protocol 0.3.0, ADR 0006, `log/2026-10-01-claude-slice3-edit-room.md`.
- Slice 2 (2026-10-01): admin Add room, protocol 0.2.0, ADR 0005, `log/2026-10-01-claude-slice2-add-room.md`.
- Slice 1 (2026-10-01): see `log/2026-10-01-claude-slice1.md` and ADR 0004.

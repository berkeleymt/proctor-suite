# 2026-10-01: Claude (chat session): Slice 6, SSE + heartbeat, design principles

**Phase item:** Phase 1 server (SSE streams) and web transport
**Directories touched:** `server/app/{stream.py,store.py,api.py}`, `server/tests/test_stream.py`, `web/src/{hooks.ts,screens/*}`, `docs/`
**Commits:** none; uncommitted for a human to review and push. Started from `2619a3b` (pulled).

## Done
- Server: `/api/rooms/{id}/stream` and `/api/staff/stream`, hub, heartbeat, notify after commit. ADR 0009.
- Web: `useLive` (SSE, backoff, dead-stream rule, polling fallback); Admin, Display, Proctor use it.
- `docs/design-principles.md` (PM's UI quality bar) linked from CLAUDE.md, specs, plan, STATUS. Low priority for now.

## Verified how
- `uv run pytest`: 76 passed, 2 skipped (real-Postgres tests, need `TEST_DATABASE_URL`). New: initial snapshot, per-room filtering, staff stream sees new rooms, heartbeat, unsubscribe on close, 401/404.
- Manual with real uvicorn + curl: staff stream received the 4 initial snapshots, then an edit made through the API arrived on the stream within a second.
- `npm run build` passes.
- NOT verified: browser behavior (EventSource reconnect, dead-stream timer, fallback to polling), Caddy/TLS buffering, many concurrent streams.

## Next steps
1. Push, deploy, open admin and a display on two devices; edit a room and watch it update instantly. Stop the app container briefly and confirm the dot goes red and recovers.
2. Reset / Hide on the admin table, then clarifications.

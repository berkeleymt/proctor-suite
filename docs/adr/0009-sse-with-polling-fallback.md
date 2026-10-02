# 0009: SSE with polling fallback (slice 6)

**Date:** 2026-10-01 · **Decided by:** Claude, following protocol §7.2-§8. No contract change (the stream endpoints were already specified; openapi unchanged).

## Decision
- `app/stream.py`: a `Hub` of subscribers. Each holds a **set of dirty room ids**, not a frame queue, so memory is bounded (invariant 8) and a slow client just gets the latest snapshot per room. `notify` is called only after the Postgres commit and the in-memory update (invariant 5), from `create_room`, `update_room`, and `apply` (when it produced an event).
- Frames are whole snapshots. Room stream: initial snapshot then changes for that room. Staff stream: one snapshot per room, then changes for any room. Heartbeat after each 15 s of quiet. Subscribe happens before the initial snapshots so no change is lost.
- Auth reuses the snapshot rules (room cookie for that room, or staff). `Cache-Control: no-cache`, `X-Accel-Buffering: no`; Caddy already has `flush_interval -1`.
- Client `useLive`: own reconnect with full-jitter backoff (not EventSource's), 35 s silence = dead, **polling runs only while the stream is down** (so first paint is fast and a proxy that blocks SSE still works, slower). Stale versions are ignored when merging.

## Not done
No ping when the server shuts down gracefully (clients reconnect via backoff). No stream connection cap or rate limit yet. No chaos tests (C1/C6/C11) or load test against many streams. Not verified through real Caddy/TLS.

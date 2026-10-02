# 0015: Bathroom log, proctor side only, as plain REST on the room snapshot

**Date:** 2026-10-02 · **Decided by:** Claude (slice 13), within ADR 0004 (wireframe is the ceiling). PM to confirm.

## Decisions
- **Scope = what the wireframe marks "New".** Proctor panel: type a student ID, **Mark out**, "Currently out" with a live "out for" time and a **Returned** button, and a "Recently returned" line. Admin Timers gets the **Out** column and "N students out" in the summary. The admin Bathroom tab (cross-room table, filters, CSV) and the Roster are marked "Later" in the wireframe and are **not built**. The "Log" drawer for single-screen rooms (display) is not built either; the wireframe only sketches it as a fallback.
- **REST, not timer commands.** Like clarifications (ADR 0011), visits are not timer events, so they stay out of the fold and its fixtures. Two endpoints, both returning the room's `RoomSnapshot` so the page updates at once; other pages get it over the existing SSE/polling.
- **Idempotent by client id** (invariant 3). The page makes one UUID per attempt and reuses it on a retry; the server treats the same id as the same visit. This is also what the phase 2 outbox needs, so nothing here has to be redone.
- **Snapshot carries it** (invariant 1: no Postgres read from a room device). `students_out` is always right; the two lists are bounded (50 out, 20 returned) and empty for staff (invariant 8). Visits live on the `Room` in memory and are written to `bathroom_visits` before memory changes (invariant 5).
- **Rules:** a student already out cannot be marked out twice; IDs are free text, trimmed and upper-cased (specs §3: no student accounts); admins and PMs may also log (the spec lets both; **superseded by ADR 0016: proctor only**); display pages may not.
- **Late highlight** at 10 minutes out, as the wireframe suggests ("about 10 minutes"); the number is a constant in `BathroomLog.tsx`, not configurable.

## Consequences
- Times are server time. The offline outbox (phase 2) must add claimed times for a student marked out while the room was offline, or the "left at" time will be when the page reconnected.
- Visits are kept for the whole day and survive a timer Reset. There is no per-day split yet; the future admin tab/export will need one if rooms are reused.
- `bathroom_visits` has `ON DELETE CASCADE`, so Empty room removes its log. Migration 0008 is additive; `deploy.sh --rollback` is safe.

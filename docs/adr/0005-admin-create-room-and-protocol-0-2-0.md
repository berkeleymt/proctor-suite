# 0005: Admin "Add room" (slice 2) bumps protocol to 0.2.0

**Date:** 2026-10-01 · **Decided by:** Claude (PM direction: wireframe is the scope ceiling; ADR 0003: no approval gate)

## Decision
- Wireframe "Create room/timer" (Admin · Timers): name + duration (default 180 min). Optional doc URL is **not** built (needs the clarifications/doc feature first).
- New endpoint `POST /api/staff/rooms` (admin/PM). Request `CreateRoomRequest` (`name` 1-60, `duration_min` 1-720). Returns `RoomSnapshot`, 201. 409 `room_exists` on a duplicate name (slug match), 422 on a name with no letters/digits.
- `room_id` is the slug of the name (`Test Hall 1` -> `test-hall-1`), as the seed rooms already do.
- Contract change: PROTOCOL_VERSION 0.1.0 -> 0.2.0, changelog line, `openapi.json` re-exported, web types regenerated.

## Known gaps (same as ADR 0004)
Still in-memory: created rooms vanish on server restart (slice 2 Postgres fixes this). No rename/delete/change-duration yet.

# 0006: Admin "Edit…" (slice 3) bumps protocol to 0.3.0

**Date:** 2026-10-01 · **Decided by:** Claude (wireframe is the scope ceiling; ADR 0003: no approval gate)

## Decision
- Wireframe Admin · Timers: Duration column, row action "Edit…" (duration, test label), and "Test label (optional)" on the Add room form.
- New `PATCH /api/staff/rooms/{room_id}` (admin/PM): `duration_min` (1-720) and/or `test_name`. `CreateRoomRequest` gains optional `test_name`.
- **Duration can only change before the timer starts** (NOT_PERMITTED or PERMITTED). After that the server returns 409 `room_started` and the UI disables the field and points to +5 min (the existing `adjust` command). Reason: the timer is derived from the event list (invariant 4); rewriting `duration` under a running timer would silently change history. The wireframe's "set remaining" is therefore covered by `adjust` for now.
- The test label can change at any time. Every edit bumps the room `version` so pollers refetch.
- Contract: PROTOCOL_VERSION 0.2.0 -> 0.3.0, changelog line, `openapi.json` re-exported, web types regenerated (the stub in `schema_app.py` was updated too).

## Not built (wireframe items still open)
Doc URL, Reset, bulk select (Start/+5 selected), confirm dialogs with Shift-skip, Hide.

## Known gaps
Still in-memory (Postgres is the next server slice). Edits vanish on restart.

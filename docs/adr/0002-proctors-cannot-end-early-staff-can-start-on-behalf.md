# 0002: Proctors cannot end a test early; staff can start a room on behalf of it

**Date:** 2026-10-01 · **Decided by:** PM · **Answers:** plan §9 open questions 3 and 4, §2.2(b), §2.2(d)

## Decision
- Proctors (room `control` devices) can only **start, pause, resume**. Ending a test before time runs out is an **Admin/PM** action (`end`).
- Admin/PM can **start a room on behalf** of the proctor (`start` sent with a staff cookie). It is the same event type as a proctor start, recorded with the staff account as actor.
- Staff cannot pause/resume in v0 (not in the spec); see protocol §13 Q2.

## Consequences
- The proctor screen has no "end" control at all.
- If a room's devices are offline and staff start it, the room shows the right time on reconnect. If the room had also started offline earlier, the earlier effective time wins (fixture 18).
- `specs.md` §2 matrix updated.

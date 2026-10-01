# 0001: Room login uses a room-name dropdown (not a typed room code)

**Date:** 2026-10-01 · **Decided by:** PM · **Supersedes:** development-plan.md §2.2(a) (original draft)

## Context
The plan proposed typing a printed room code (e.g. `EVANS60`) as the username, to avoid dropdown misclicks. `specs.md` §5 already specifies a room-name dropdown plus one shared event password.

## Decision
Keep the dropdown. The room is the "username"; one event password for all rooms. The dropdown is filled by a public, bounded endpoint, `GET /api/auth/rooms` (≤ 500 rooms).

## Consequences
- After login the UI must show the room name huge with "Is this your room?" before enabling anything, and the staff dashboard shows device counts per room (these are the guard against a misclick).
- The room list is visible to anyone who can reach the server (protocol §13 Q3). Accepted for v0.
- The printed room packet should show the event password and the exact room name.
- No `rooms.code` column is needed.

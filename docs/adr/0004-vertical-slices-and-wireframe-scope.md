# 0004: Build in thin vertical slices; the wireframe is the scope ceiling

**Date:** 2026-10-01 · **Decided by:** PM (direction), Claude (slice 1 details)

## Decision
- Build one small feature at a time, server and web together, deployable after each. Not "all server, then all web".
- `docs/wireframe.html` (from the project lead) is the scope ceiling: nothing outside it. It lists features, not mechanisms; the mechanisms stay in `protocol.md`.
- Slice 1 shortcuts (all temporary, each removed by a later slice):
  1. **In-memory store, no Postgres.** Breaks invariant 5 until slice 2. Prod data resets on restart. Not for a real event.
  2. **Polling** (`/snapshot?since_version`, every 2 s) instead of SSE. Allowed by protocol §7.3; SSE is slice 3.
  3. **Env passwords**: `ROOM_PASSWORD` (all rooms), `ADMIN_PASSWORD` (one `admin` account). Sessions are in memory, so a server restart logs everyone out.
  4. **No login rate limiting** yet (protocol §3 asks for it).
  5. **Rooms seeded from `SEED_ROOMS`**, no add-room UI yet.
- UI follows apple-design/animate basics: system fonts only (invariant 6), press feedback on pointer-down, transform/opacity-only motion under 250 ms, `prefers-reduced-motion` honored.

## Consequences
The wireframe items not in the protocol (clarifications, bathroom log, chat, roster, deletion, super-admin) need new protocol sections and a version bump before they are built. Chat is marked "Decision" in the wireframe and is not built until the PM says so.

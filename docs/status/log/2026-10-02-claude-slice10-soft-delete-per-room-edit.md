# 2026-10-02: Claude (chat session): Slice 10, soft delete + Empty, per-room edit, live list, header, Auto size

**Phase item:** Phase 1 stretch: PM's six follow-ups to slice 9
**Directories touched:** `server/{app,alembic,tests}`, `web/src`, `docs/`
**PR / commits:** none; uncommitted (patch file). Started from `a9bb1b8`.

## Done (numbers are the PM's list)
1. Auto clarification size now lands three ¶− steps below the largest size that fits (capped at what fits).
2. Quiet "Clarifications" heading above the list on the display (muted, `clamp(18px, 3.4vh, 40px)`).
3. Clarifications header: counts (posted · showing · hidden · Show deleted), then the light and Log out at the right. `LogoutButton` is shared with Timers.
4. Admin list updates live (SSE `clarifications` event, polling fallback). Delete is soft; "Show deleted" shows them in the same tab with Restore. Deletion tab removed from the wireframe, plan, spec, design principles, status.
5. Empty… (permanent, confirmed) for deleted clarifications and deleted rooms. Per-room deletes are restorable in the Rooms popover.
6. Per-room Edit… in the Rooms popover: the room moves to its own edited copy; others unchanged.

## Verified how
- `py_compile` on all changed Python; TypeScript syntax check of the changed TSX (transpile only).
- NOT run: `uv run pytest`, `ruff`, `npm run build`, any browser. The sandbox has no network, so no Python 3.13, no deps, no node_modules. New tests are written but unrun: `test_per_room_edit_makes_a_copy_for_that_room`, `test_empty_room_wipes_it_and_forgets_it`, updated delete/per-room tests, and the Postgres restart test.
- `contracts/openapi.json` and `web/src/api-types.ts` are NOT regenerated (a test fails until they are). `web/src/api.ts` extends `Clar` by hand so the build compiles either way.

## Not done / blocked
- Preview-display button; the "Clarifications" heading is not shown over the Google Doc iframe.
- (Closed in the same slice) live room list on the Clarifications page, `room_removed` stream event, stream tests `test_staff_stream_clarifications_event_and_room_removed` and `test_staff_stream_without_flag_sends_no_clarifications`; also unrun.

## Decisions made
- ADR 0013.

## Next steps
1. Regenerate the contract, run pytest, ruff, `npm run build`. Fix whatever the first real run finds.
2. Deploy (migration 0005). In a browser: post, delete, Show deleted, Restore, Empty; per-room Edit on an "All rooms" post with two displays open; two admin windows to watch the live update; projector at real size for Auto and the heading.

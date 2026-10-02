# 0013: Soft delete + Empty for clarifications and rooms, per-room edit, live admin list, no Deletion tab

**Date:** 2026-10-02 · **Decided by:** PM (items below), implemented by Claude (slice 10). Supersedes the "Delete wipes the row" part of ADR 0012.

## Decisions
- **There is no Deletion tab.** Removed from the wireframe, plan, spec and status docs. Deleted rooms and clarifications live on the tab they belong to behind "Show deleted (n)" in the header, the same way deleted rooms already did. One pattern, learned once (design principle 0).
- **Nothing is really deleted until someone presses Empty.** Clarification `DELETE` is now soft (`deleted` flag; per-room: `removed_room_ids`). Deleted ones show with **Restore** and **Empty…**. Per-room deletes are restored from the Rooms popover. A deleted clarification cannot be edited or hidden.
- **Empty** wipes the record from the database for good, after a confirm dialog (Cancel, then a red "Empty"). Only works on something already deleted. Clarification: `POST .../empty`. Room: `POST /api/staff/rooms/{id}/empty` also deletes its commands and removes the room from every clarification (one left with no rooms becomes deleted, restorable). The name can be reused afterwards.
- **Per-room edit** (`PATCH {body, room_id}`): that room moves to a new copy carrying the edited text (old wording crossed out as with any edit); the other rooms keep the original. Original keeps its row; for an "All rooms" post it records `edited_room_ids` so rooms created later still get the original. If the post only reaches that room it is a plain edit. The copy keeps the original's post time so the order in that room does not change.
- **Live admin list.** `GET /api/staff/stream?clarifications=1` adds a `clarifications` event (full admin list, max 200) on connect and after each change; polling is the fallback. Room devices are untouched (they already got changes through their snapshot).
- **Clarifications header** matches Timers: tabs, counts (posted, showing, hidden, Show deleted), then the connection light and Log out at the right. Log out is now one shared component.
- **Projector.** Auto clarification size = the size three ¶− clicks below the largest that fits (never larger than what fits). A quiet "Clarifications" heading sits above the list.

## Consequences
Protocol 0.8.0, migration 0005 (additive; `--rollback` safe). The Clarifications page reads its rooms from the same staff stream as Timers, so rooms added, renamed, deleted or emptied by another admin show up at once; it holds two staff streams (rooms, and the clarification list). The staff stream sends `room_removed` after an Empty so no admin page keeps a wiped room. A room emptied while someone is typing is dropped from the pick at Post time.

# 0011: Clarifications, smallest useful version

**Date:** 2026-10-01 · **Decided by:** Claude (slice 8), for the PM to review

## Decision
- Scope is the wireframe's Admin · Clarifications tab only: composer, room chips (All, Clear, by building, by test), posted list with Hide/Unhide, and the projector list. Not built yet: Edit, Preview display, markdown/MathJax, paragraph zoom (¶−/¶+), per-room deletion and the Deletion tab.
- Clarifications live in the room snapshot (`clarifications`, visible ones only, max 50, oldest first). No new device loop, so offline and polling behavior stay as they were.
- One post can target several rooms, stored once with `room_ids` (null = all rooms, so rooms created later get it too). If the admin selects every room, we send null.
- Version trick: store-wide `clar_rev` is added to each room's `version`. Posting to 200 rooms writes one row, not 200 room rows. It is rebuilt at startup as `max(rev)`, so versions never go backwards after a restart.
- Staff room list and stream carry `clarifications: []` to keep the dashboard payload small.
- Text only: lines starting `- ` become bullets. We did not bundle a markdown/MathJax library yet (invariant 6: no CDN; bundle size is for a later slice).
- Permissions: admin and PM may post (the spec's Test Organizer role does not exist yet).
- Display font shrinks (44 px down to 12 px) until the list fits in at most 38% of the screen height; hidden once the timer is ENDED (swire behavior).

## Consequences
Protocol 0.6.0. Migration `0003` adds `clarifications`. The admin list refreshes after your own actions only; a second admin sees changes after a reload.

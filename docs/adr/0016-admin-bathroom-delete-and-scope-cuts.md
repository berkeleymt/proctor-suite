# 0016: Admin Bathroom tab, who may record and delete, and wireframe items cut

**Date:** 2026-10-02 · **Decided by:** PM (roles, cuts, proctor list look), Claude (mechanisms, slice 14)

## Decisions (PM)
- **Proctors record and view; admins view and delete. Nobody else.** Recording a student out or back is now that room's proctor only; admins and PMs get 403 (this reverses the "admins may also log" line of ADR 0015). Proctors have no delete at all.
- **Admins can delete individual records, a ticked selection, or all records.** "Dangerously": a typed `DELETE` confirmation that says how many students are out right now and will vanish from their proctors' lists.
- **The proctor's "recently returned" line is gone.** Returned students are rows in the same list as the ones who are out, same shape, **faded** (the way deleted rooms and clarifications look when revealed). Out now first, then returned, most recent first, at most 20 (`MAX_BATHROOM_BACK`).
- **Cut from the wireframe, on purpose** (so nobody builds them later without a new decision): bathroom on the projector display (no Log drawer, no projector mirror); chat with admins (all chat stays in Discord); the "Preview display" button in Clarifications (the composer already has a preview).

## Decisions (Claude)
- **Delete is soft**, like rooms and clarifications (design principle 0, ADR 0013): the record is hidden behind "Show deleted (n)" with **Restore** and a confirmed, red **Empty** (permanent, only on already-deleted records). "Delete all" and "Empty all" are explicit buttons, not a hidden default. A deleted record that was still "out" stops counting as out and stops blocking that student from going out again; restoring it is skipped if that would put the same student out twice in one room.
- **One endpoint for the three actions** (`POST /api/staff/bathroom/action`, `ids` or `all`) instead of three: less contract and less client code. It runs per room under that room's lock, Postgres first then memory (invariant 5), and bumps each touched room's version so proctor pages update on their own.
- **No polling on the admin page.** It already holds the staff stream (for the room list and the connection light); whenever the sum of room versions moves, it refetches the list (throttled to once per 1.5 s). Filters (room, Out now / Returned / All, search) run on the server so the default view ("Out now") stays tiny.
- **CSV export is client-side** from a `limit=5000` request for the chosen room, all statuses (the "after the test" record, not just whoever is out at that moment). One file per room is the fallback past 5000.
- Admin bathroom and roster reads come from memory; nothing here touches Postgres on read.

## Consequences
- `deploy.sh` runs migration 0009 (additive: `bathroom_visits.deleted`; `--rollback` is safe, the old code ignores the column).
- Names reach proctor pages only on that room's next change (the roster import does not push every room). Acceptable: the name is a help.
- There is still no per-day split of records; Delete all is the end-of-test cleanup.

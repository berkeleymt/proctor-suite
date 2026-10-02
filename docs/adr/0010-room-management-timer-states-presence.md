# 0010: Room management, timer states, and presence (protocol 0.4.0)

**Date:** 2026-10-01 · **Decided by:** PM (reset lands on Not started; reset only from paused/finished), Claude (details). Contract bumped to 0.4.0.

## Timer states and who can do what
| State | Proctor | Admin / PM |
|---|---|---|
| Not started | Start (disabled: "unlocks when an admin allows it") | Allow start |
| Ready (allowed) | Start | Start |
| Running | Pause | Pause, +5 min |
| Paused | Resume | Resume, Reset, +5 min |
| Finished | nothing ("Time's up") | Reset |
- Staff can now pause and resume (closes protocol open question 2).
- **Reset** = a new timer session (`session_seq + 1`, new `session_created_ms`, events emptied in memory). It lands on **Not started**, so an admin must Allow start again. Only from PAUSED or ENDED; a running timer must be paused first. History is kept in Postgres (old sessions' rows stay) and an audit row (`type = reset`, `is_event = false`) is written in the same transaction. Taps still in flight from the old session are rejected as `stale_session` by the existing rule. The request carries the `session_id` the admin saw, so two admins can't reset twice.

## Room management (all on the Timers table; the wireframe has no separate rooms page)
- **Rename:** the `room_id` never changes (cookies, history). Names are unique case-insensitively. Known quirk: a deleted or renamed room's old id still blocks creating a room whose name slugs to it.
- **Delete** (wireframe: Admin · Deletion) is a **soft delete** (`deleted` flag): hidden from the login list, snapshots, streams and commands; the room's sessions are removed so proctors are signed out; its open stream ends. Not allowed while RUNNING or PAUSED (in progress). **Restore** from "Show deleted". Deviation from the wireframe: it says "Shift skips confirm" but also shows "Type DELETE"; since sign-out can't be undone we always require typing DELETE, no Shift skip.
- **Doc link** (`doc_url`, https only) is stored and editable; nothing displays it yet (needs the clarifications feature).
- Migration `0002` adds `session_seq`, `session_created_ms`, `deleted`, `doc_url` to `rooms`. Additive, so `--rollback` stays safe.

## Presence
- Derived from open SSE streams: each device page says `?surface=control|display`, and it only counts when that surface's cookie is valid for that room. The staff stream sends a `presence` event per change; the admin table shows "Proctor" and "Display" with a green dot (open now, "x2" if several devices) or a grey ring (tooltip: last seen, or never opened), plus a filter ("No proctor page", "No projector page", "Neither open") to find rooms where someone is stuck.
- Memory only; a server restart forgets it until devices reconnect. It measures open pages, not logins: a proctor who logged in and then closed the tab shows grey with a last-seen time.

## Consistency work
Shared `Sheet` (all dialogs), `Menu` (row "more actions"), `Dot` (connection light, always right-aligned in the header, fixing the proctor screen where it sat off to the side). Principle recorded in `design-principles.md`.

## Not done
Display of the doc link, bulk reset, audit viewer, devices count beyond "x2", bulk Pause/Resume.

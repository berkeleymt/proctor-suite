# 0017: Roster from a CSV first; ContestDojo's API is an optional extra

**Date:** 2026-10-02 · **Decided by:** Claude (slice 14), PM to confirm. PM asked for typing a student ID to show their name and info for proctors and admins alike.

## What we found out about ContestDojo's API (github.com/contestdojo/api, read 2026-10-02)
- It is the **source of a self-hosted service** (Starlette on Firestore), not documentation of a public one. The repo has no README, **no base URL**, and was **archived on 2026-07-22**.
- Roster data is `GET /events/{event_id}/students/` (fields: `number`, `fname`, `lname`, `email`, `org`, `team`, `roomAssignments`, `isCheckedIn`), plus `/teams/` and `/orgs/` for names. All are admin-only.
- Auth is `Authorization: Bearer <token>` where the token is an **opaque string that exists as a document in the `api_tokens` Firestore collection** (or an OAuth JWT, but OAuth tokens only reach `/v1alpha1/me/...`, a student's own registration, never a roster). A ContestDojo website login cannot mint such a token; someone with Firestore access has to.

So: whether we can use the API at all depends on ContestDojo's maintainers giving us a base URL and a token. We cannot verify that today.

## Decisions
- **Primary path: CSV import.** The Roster tab has "Import CSV…" (choose a file or paste). Headers are matched loosely (ID/Student ID/Number; Name or First+Last; School/Org; Team; Room; Contact). It works with no network, no token and no dependency on anyone, and it is fully tested. The whole roster is replaced on import (never merged), in one transaction.
- **Optional path: Sync.** If `CONTESTDOJO_API_URL`, `CONTESTDOJO_API_TOKEN` and `CONTESTDOJO_EVENT_ID` are set, the Roster tab shows **Sync**. The server reads students, teams and orgs (20 s timeout, in a thread so timers never stall) and replaces the roster. Mapping: ID = student `number` (what a proctor types, e.g. `054A`; **assumed, PM to confirm**), school = org name, team = team name, contact = student `email`, room = `roomAssignments[CONTESTDOJO_ROOM_KEY]` only if that key is set (the dict's shape is unknown). Tested against a fake; **never run against the real service**.
- **Never on the event-day critical path** (invariant 6): import/sync is an admin action done before the event. The roster lives in Postgres and memory; a proctor's lookup is one in-memory read (invariant 1), returns one student (invariant 8), and works if ContestDojo is down.
- **Who sees what:** proctors get name, school, team and room only. **Contact details are admins-only** (parents and coaches, students are minors). A proctor is warned when a student is assigned to a different room ("assigned to Soda 306") but can still mark them out.
- **Name is a help, never a gate:** an unknown ID can still be marked out ("Not on the roster. You can still mark them out.").
- Names are resolved when lists are built, so a roster imported late fills in names on earlier records.

## Consequences
- The roster is personal data about minors, stored in the app's Postgres. There is no "clear roster" button yet; after the event wipe it with `DELETE FROM roster_students;` (steps in `docs/setup-contestdojo.md`) or `docker compose down -v`. Worth a button before Nov 14 if the PM wants it.
- If ContestDojo gives us a token, only the field mapping above needs checking against one real response (`GET /events/{id}/students/`), not a redesign.


## Update 2026-10-02
- The "Clear roster" button now exists (ADR 0018); the SQL is only a fallback.
- Sync is still unverified against the real API. We are waiting on the ContestDojo maintainers to guide us; this is the only open Phase 1 item (`status/STATUS.md`).

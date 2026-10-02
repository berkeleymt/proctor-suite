# Project status

**Last updated:** 2026-10-02 (slice 15) · **Event:** BMT, Sat Nov 14, 2026 · **Feature freeze:** Nov 1 · **Total freeze:** Nov 11

## Where we are

**Phase 0 (Foundations): COMPLETE.** **Phase 1 (Prototype): feature-complete and live; one blocker left.** Details in [`phase-0.md`](phase-0.md) and [`phase-1.md`](phase-1.md).

- Prod is deployed through `deploy.sh` (migrations 0001-0009 applied), `/healthz` is `ok`, `/readyz` is `ready`, GitHub CI is green, and every screen has been checked in real browsers *(reported by the PM, 2026-10-02)*.
- Built: login, proctor timer (Start / Pause / Resume, zoom), projector display, admin Timers (add, edit, delete/restore/empty, filters, bulk actions, presence), Clarifications, proctor Bathroom log, admin Bathroom log, Roster (ContestDojo Sync only, settings on `/super`, **Clear roster**), branding and `/super`. Protocol is **0.12.0** (history in [`protocol.md`](../protocol.md) §14). Server: 117 tests pass without Postgres (the real-Postgres set was 124 before slice 15 and was not re-run for it).
- Scope ceiling is `docs/wireframe.html`. Cut by the PM ([ADR 0016](../adr/0016-admin-bathroom-delete-and-scope-cuts.md)): chat, bathroom on the projector, Preview-display button. Not needed ([ADR 0018](../adr/0018-clear-roster-and-proctor-log-layout.md)): a student dropdown in the proctor log. No Deletion tab ([ADR 0013](../adr/0013-soft-delete-empty-per-room-edit-no-deletion-tab.md)).

## Blocker (the only open Phase 1 item)

**ContestDojo Sync has never run against the real API.** We are waiting for the ContestDojo maintainers to walk us through it: base URL, token, event ID, and one real `GET /events/{id}/students/` response so we can confirm the ID (`number`) and `roomAssignments` mapping. See [ADR 0017](../adr/0017-roster-csv-first-contestdojo-optional.md) and [`setup-contestdojo.md`](../setup-contestdojo.md). CSV import works in prod today, so the event does not depend on Sync.

## Next actions, in order

1. **ContestDojo Sync** with the maintainers (above). Immediate next step; do the field-mapping check on one real response, then press Sync on prod and spot-check a real student ID on `/proctor`.
2. **Chaos C1, C6, C11 and the Oct 5 demo** (3+ devices, one room, plus the admin page, on AWS). Manual steps and a place to record results: [`chaos-phase1.md`](../chaos-phase1.md). Forrest decides whether the gate is green; record the date, devices and outcome in `phase-1.md`.
3. **Phase 2 (Oct 6 - Oct 18):** outbox, merge rules, Service Worker, wake lock, presence/system page, staff "start on behalf". Forrest writes the Playwright chaos suite in parallel (`web/e2e/`, doesn't exist yet), which replaces the manual C1/C6/C11 steps.
4. Before Nov 14: after the event, use **Roster -> Clear roster...** (students are minors). Bathroom log: **Delete all...** then **Show deleted -> Empty all...** if it shouldn't be kept.

## Open, non-blocking

- Server gaps from `phase-1.md`: no rate limiting; sessions are in memory (people sign in again after a restart).
- Protocol §13: adding time after expiry; staff pause/resume; public room list in the login dropdown.
- Optional ADRs for D1-D4 and D7; `server/CLAUDE.md`; `infra/README.md`.
- AWS hygiene (shared email, MFA, budget alert) and backups/monitoring/staging are not verified.
- Proctor log: a returned row jumps to the "Back" group while it fades (no FLIP slide). Fine for now; polish pass before Oct 31 ([`design-principles.md`](../design-principles.md)).

## Phase overview

| Phase | Planned dates | State |
|---|---|---|
| 0 Foundations | Sep 26 - Sep 29 | **Done** (Oct 1) |
| 1 Prototype | Sep 30 - Oct 5 | Features done and deployed; open: ContestDojo Sync check, C1/C6/C11, Oct 5 demo |
| 2 Offline core | Oct 6 - Oct 18 | Not started |
| 3 Surfaces | Oct 6 - Oct 24 | Mostly built early (clarifications, bathroom, roster); exports and polish left |
| 3b Hardening | Oct 19 - Oct 30 | Not started |
| 4 Dress rehearsal | Oct 31 | Not started |

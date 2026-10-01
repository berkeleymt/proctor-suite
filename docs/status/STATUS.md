# Project status

**Last updated:** 2026-10-01 · **Event:** BMT, Sat Nov 14, 2026 · **Feature freeze:** Nov 1 · **Total freeze:** Nov 11

## Where we are

**Phase 0 (Foundations): COMPLETE** (pending push of today's files and a green CI run on them). Details in [`phase-0.md`](phase-0.md).

- AWS prod is live and CI is green *(reported by the PM, 2026-10-01)*.
- The contract exists: [`docs/protocol.md`](../protocol.md) v0.1.0, `contracts/openapi.json`, 23 timer fixtures, Pydantic models, and a reference fold that passes all fixtures.
- Decisions made today: D1–D12 approved; proctors cannot end early; staff can start on behalf; login is a room-name dropdown; no approval gate on contract changes (ADRs 0001–0003).

**Phase 1 (Prototype): not started.** Demo target Mon Oct 5. Checklist in [`phase-1.md`](phase-1.md).

## Next actions, in order

1. Commit and push the Phase 0 files; confirm CI is green.
2. Start Phase 1 tickets: Ian on server (schema, auth, commands, SSE); Forrest on `web/` scaffold, `sync-core`, login/display/control screens.
3. Generate the TS types from `contracts/openapi.json` as the first `web/` ticket.

## Open, non-blocking

- Protocol §13: adding time after expiry; staff pause/resume; public room list in the login dropdown.
- Optional ADRs for D1–D4 and D7; `server/CLAUDE.md`; `infra/README.md`.
- AWS hygiene (shared email, MFA, budget alert) and backups/monitoring/staging are not verified.

## Phase overview

| Phase | Planned dates | State |
|---|---|---|
| 0 Foundations | Sep 26 – Sep 29 | **Done** (Oct 1) |
| 1 Prototype | Sep 30 – Oct 5 | Not started |
| 2 Offline core | Oct 6 – Oct 18 | Not started |
| 3 Surfaces | Oct 6 – Oct 24 | Not started |
| 3b Hardening | Oct 19 – Oct 30 | Not started |
| 4 Dress rehearsal | Oct 31 | Not started |

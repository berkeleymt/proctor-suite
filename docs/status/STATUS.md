# Project status

**Last updated:** 2026-10-01 (slice 4) · **Event:** BMT, Sat Nov 14, 2026 · **Feature freeze:** Nov 1 · **Total freeze:** Nov 11

## Where we are

**Phase 0 (Foundations): COMPLETE** (pending push of today's files and a green CI run on them). Details in [`phase-0.md`](phase-0.md).

- AWS prod is live and CI is green *(reported by the PM, 2026-10-01)*.
- The contract exists: [`docs/protocol.md`](../protocol.md) v0.1.0, `contracts/openapi.json`, 23 timer fixtures, Pydantic models, and a reference fold that passes all fixtures.
- Decisions made today: D1–D12 approved; proctors cannot end early; staff can start on behalf; login is a room-name dropdown; no approval gate on contract changes (ADRs 0001–0003).

**Phase 1 (Prototype): in progress, slices 1-3 pushed; slice 4 (Postgres persistence, bulk select, ADR 0007) written, not pushed. Nothing verified in a browser or deployed yet.** Demo target Mon Oct 5. Checklist in [`phase-1.md`](phase-1.md).

- Slice 1 = login → proctor Start/Pause/Resume → display timer → admin Allow/Start/+5. Server tests pass (71). UI not yet tried in a browser. Slice 4 added Postgres persistence (rooms and commands; sessions still in memory); still polling, not SSE. See ADR 0004 and `log/2026-10-01-claude-slice1.md`.
- Scope ceiling is `docs/wireframe.html`. Chat, clarifications, bathroom log, roster, deletion, super-admin need protocol additions first.

## Next actions, in order

1. Push slice 4 and run `deploy.sh` (README). It now runs the first Alembic migration. Try login, Add room, Edit, bulk Start on 2 devices.
2. After deploy: `/readyz` says `ready`; restart the app container and confirm rooms and running timers survive.
3. Slice 5: SSE + heartbeat (replaces polling). Then Reset / Hide.

## Open, non-blocking

- Protocol §13: adding time after expiry; staff pause/resume; public room list in the login dropdown.
- Optional ADRs for D1–D4 and D7; `server/CLAUDE.md`; `infra/README.md`.
- AWS hygiene (shared email, MFA, budget alert) and backups/monitoring/staging are not verified.

## Phase overview

| Phase | Planned dates | State |
|---|---|---|
| 0 Foundations | Sep 26 – Sep 29 | **Done** (Oct 1) |
| 1 Prototype | Sep 30 – Oct 5 | In progress (slice 1 written) |
| 2 Offline core | Oct 6 – Oct 18 | Not started |
| 3 Surfaces | Oct 6 – Oct 24 | Not started |
| 3b Hardening | Oct 19 – Oct 30 | Not started |
| 4 Dress rehearsal | Oct 31 | Not started |

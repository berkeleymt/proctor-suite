# Project status

**Last updated:** 2026-10-02 (slice 12) · **Event:** BMT, Sat Nov 14, 2026 · **Feature freeze:** Nov 1 · **Total freeze:** Nov 11

## Where we are

**Phase 0 (Foundations): COMPLETE** (pending push of today's files and a green CI run on them). Details in [`phase-0.md`](phase-0.md).

- AWS prod is live and CI is green *(reported by the PM, 2026-10-01)*.
- The contract exists: [`docs/protocol.md`](../protocol.md) v0.1.0, `contracts/openapi.json`, 23 timer fixtures, Pydantic models, and a reference fold that passes all fixtures.
- Decisions made today: D1–D12 approved; proctors cannot end early; staff can start on behalf; login is a room-name dropdown; no approval gate on contract changes (ADRs 0001–0003).

**Phase 1 (Prototype): in progress. Slices 1-6 are pushed; slice 7 is pushed; slices 8-10 (clarifications; edit/delete/markdown/projector layout; soft delete + Empty, per-room edit, live admin list) are written, not pushed. Nothing is verified in a browser, and the Oct 5 demo gate has not been run.** Demo target Mon Oct 5. Checklist in [`phase-1.md`](phase-1.md).

- Built so far: login → proctor Start/Pause/Resume (+ zoom) → projector display (fits any screen, zoom) → admin timers table (add, rename, edit, delete/restore, filter, per-state actions incl. reset, bulk allow/start/+5/edit/delete, device presence). Server tests pass (86 with a real Postgres; 83 + 3 skipped without). UI not yet tried in a browser. Slice 4 added Postgres persistence (rooms and commands; sessions still in memory); slice 6 replaced polling with SSE (polling is the fallback). See ADR 0004 and `log/2026-10-01-claude-slice1.md`.
- Scope ceiling is `docs/wireframe.html`. Chat, bathroom log, roster, super-admin need protocol additions first. There is no Deletion tab (ADR 0013).

## Next actions, in order

-1. Slice 12: add `APP_NAME` / `APP_ICON` to prod `.env` (compose requires `APP_NAME`), do DNS and Google setup ([`setup-domain-and-google.md`](../setup-domain-and-google.md)), then deploy (migration 0007).

0. *(Done in slice 11)* Contract regenerated; pytest 98 passed with Postgres, `npm run build` passes.
1. Push slices 8-10 (migrations 0003-0005) and run `deploy.sh` (README). Open `/display` on a real projector or a resized window and click through login, Add room, filters, bulk actions on 2 devices. **Browser verification is the biggest open risk.**
2. After deploy: `/readyz` says `ready`; restart the app container and confirm rooms and running timers survive.
3. Slices 9-10 are done except the Preview-display button (ADR 0012, 0013); the Deletion tab was cancelled. Check a Google Doc embed on a real display.

## Open, non-blocking

- UI polish bar for later: [`design-principles.md`](../design-principles.md). Not a priority until features land.

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

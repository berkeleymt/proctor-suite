# 2026-10-01: Claude (chat session): contract sprint

**Ticket / phase item:** Phase 0 §C (contract sprint), gate
**Directories touched:** `docs/`, `contracts/`, `server/app/protocol/`, `server/app/fold.py`, `server/scripts/`, `server/tests/`, `CLAUDE.md`, `specs.md`, `development-plan.md`
**PR / commits:** none; left uncommitted for the team to commit

## Done
- Recorded PM decisions: D1–D12 approved; proctors cannot end early; staff start-on-behalf yes; room-name dropdown login; no approval gate.
- Wrote `docs/protocol.md` v0.1.0, `server/app/protocol/{constants,models,schema_app}.py`, `server/scripts/export_openapi.py`, `contracts/openapi.json`.
- Wrote the reference fold `server/app/fold.py` and 23 fixtures in `contracts/timer-fixtures/` (expected values typed by hand, then checked against the fold).
- Tests: `test_timer_fixtures.py`, `test_fold_rules.py`, `test_protocol.py`. 67 pass in total.
- Updated `development-plan.md` (login, §2.2 b/d, §9, D9, §7.3 note), `specs.md` (§2 matrix, §11 SSE, PM export), `CLAUDE.md`.
- Added ADRs 0001–0003, `phase-1.md`, refreshed `STATUS.md` and `phase-0.md`.

## Verified how
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`: all green (67 tests).
- Mutation check: changing one fixture value, or changing the fold's sort key, makes tests fail.
- NOT verified: GitHub CI on these files (not pushed); AWS (taken from the PM's statement).

## Not done / blocked
- TS type generation (no `web/` yet).
- ADRs for D1–D4/D7, `server/CLAUDE.md`, `infra/README.md`.

## Decisions made
- ADR 0001 (dropdown login), 0002 (end/start-on-behalf), 0003 (no contract approval gate).
- Judgement calls inside protocol v0.1.0 that the PM didn't explicitly decide: once time hits zero staff cannot add time; staff cannot pause/resume; public room list for the dropdown. All listed in protocol §13.

## Next steps for whoever picks this up
- Push, confirm CI green, then start `phase-1.md`.

# 2026-10-02: Claude: slice 14, admin Bathroom log, roster, proctor list cleanup

**Ticket / phase item:** Phase 1, wireframe "Bathroom log (admin)" and "Roster" (both "Later" in the wireframe; PM pulled them in). Completes the Phase 1 feature list.
**Directories touched:** `server/`, `web/`, `contracts/`, `infra/`, `docs/`
**PR / commits:** not committed (files patched in the working tree on top of `655c24c`)

## Done
- Server: migration `0009` (`bathroom_visits.deleted`, `roster_students`); `app/roster.py` (CSV parser with loose headers, optional ContestDojo fetch); `Store.bathroom_list` / `bathroom_action` / `replace_roster` / `out_since`; names and soft-delete in snapshots; 6 endpoints (`/api/staff/bathroom`, `.../action`, `/api/staff/roster`, `.../import`, `.../sync`, `/api/roster/lookup`). Recording now proctor-only. Protocol 0.11.0, `openapi.json` and `api-types.ts` regenerated. Response fields made required-but-nullable (also fixed `BathroomVisit.back_ms`).
- Web: `AdminBathroom.tsx`, `Roster.tsx`, tabs "Bathroom log" and "Roster" in the shared `AdminBar`; `useFetched` / `useDebounced` / `stampOf` in `hooks.ts` (list refetches when the staff stream says something changed, no polling); proctor `BathroomLog.tsx` rewritten (one list, returned rows faded, name line under the ID field, no "Recently returned" `<details>`).
- Infra/docs: `CONTESTDOJO_*` env passthrough, `.env.example`, README, `docs/setup-contestdojo.md`, protocol §7.7-7.8, ADRs 0016 and 0017 (0015 partly superseded).

## Verified how
- `cd server && uv run pytest -q`: 116 passed, 8 skipped (no Postgres).
- With Postgres 16 (`TEST_DATABASE_URL=postgresql://t:t@localhost:5432/t`): **124 passed**, including `test_bathroom_delete_and_roster_survive_restart` (migration 0009, restart, delete/restore/empty, roster replace).
- `uv run ruff check . && uv run ruff format --check .` clean. `cd web && npm run gen && npm run build` passes.
- New tests (`tests/test_bathroom_admin.py`): list counts/filters/order/limit, proctor cannot read or delete (401), soft delete + proctor view + restore skip + empty rules, action validation, roster import/lookup (no contact for proctors)/list/filters/permissions/errors/replace, CSV header spellings, sync not configured / configured / failure keeps old roster, ContestDojo field mapping and plain errors (all against fakes).

## Not done / blocked
- **Not tried in a browser** (none in the sandbox): layout of the two new tabs, faded rows, name line, CSV download, file picker, phone width.
- **ContestDojo sync has never touched the real API.** Needs a base URL and token from ContestDojo (ADR 0017, `setup-contestdojo.md`); the ID-is-`number` and `roomAssignments` assumptions are unchecked. CSV import is the path that is actually verified.
- No "Clear roster" button (privacy cleanup is a one-line SQL in the setup doc).
- Names reach an open proctor page only on that room's next change.

## Decisions made (ADRs 0016, 0017)
- PM: proctors record and view, admins view and delete; delete one / selected / all behind typed DELETE; returned list = faded rows; no projector bathroom, no chat, no Preview-display button.
- Claude: soft delete with Restore / Empty (consistency); one action endpoint; admin page rides the staff stream; CSV first, API optional; contacts admins-only; name is a help not a gate.

## Next steps for whoever picks this up
- Deploy (migration 0009), import a roster, run the two-device check in STATUS "Next actions".
- Ask ContestDojo for the base URL, token and event ID if Sync is wanted; check one real student JSON.
- Then the Oct 5 gate: demo with 3+ devices, chaos C1/C6/C11.

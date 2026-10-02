# 2026-10-01: Claude (chat session): Slice 7, timer states + room management + presence

**Phase item:** Phase 1: timer functionality (reset, staff pause/resume), admin room management, device presence
**Directories touched:** `server/{app,alembic,tests}`, `contracts/openapi.json`, `web/src/{api.ts,hooks.ts,components/ui.tsx,screens/*,styles.css}`, `docs/`
**Commits:** none; uncommitted for a human to review and push. Started from `84337b5` (pulled).

## Done
- Status dot right-aligned on the proctor screen (shared `Dot`, `.bar > .dot { margin-left: auto }`).
- Timer states per PM list (ADR 0010): admin Pause/Resume/Reset, proctor "Time's up" when finished, hints explaining disabled buttons.
- Room management: rename, soft delete (type DELETE), restore, doc link; bulk Delete.
- Presence: Proctor / Display dots per room, filter "Pages open"; staff stream `presence` event.
- Shared UI: `Sheet`, `Menu`, `Dot`. "Consistent" added to `design-principles.md`.
- Protocol 0.4.0 (changelog, endpoints, matrix, open question 2 resolved), migration `0002`.

## Verified how
- `uv run pytest` with `TEST_DATABASE_URL` against local PostgreSQL 16: 86 passed (new: reset rules incl. stale session and in-flight tap, proctor can't reset, delete/restore/rename/doc link, in-progress rooms can't be deleted, presence counting and last-seen, deleted room's stream ends, migrations 0001+0002, reset/delete/rename survive a restart). ruff clean.
- Real uvicorn + curl: presence event went online 1 then 0 with last-seen when a proctor stream opened and closed; deleting a room made that proctor's next request 404.
- `npm run build` passes.
- NOT verified: any of the UI in a browser (menu popover, sheets, filters, presence dots, timer-state buttons), docker compose with migration 0002, prod.

## Not done
Display of the doc link, bulk reset, audit viewer, clarifications, bathroom log.

## Next steps
1. Push, deploy (migration 0002 runs in `deploy.sh`), click through every timer state as admin and proctor on two devices.
2. Clarifications (needs a protocol addition; also fills the display's clarifications area and doc link).

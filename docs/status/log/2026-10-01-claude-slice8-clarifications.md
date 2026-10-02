# 2026-10-01: Claude (chat session): Slice 8, clarifications (minimal)

**Phase item:** Phase 1 stretch: clarifications (wireframe: Admin · Clarifications, Display)
**Directories touched:** `server/{app,alembic,tests}`, `contracts/openapi.json`, `web/src/{api.ts,api-types.ts,main.tsx,styles.css,components/*,screens/*}`, `docs/`
**PR / commits:** none; uncommitted for a human to review and push. Started from `ca92114`.

## Done
- Server: table + migration `0003`, store (post/hide, per-room visibility, `clar_rev` versioning), 3 endpoints, snapshot field, protocol 0.6.0, OpenAPI re-exported.
- Web: admin tabs (Timers | Clarifications), `/admin/clarifications` (composer, room chips with shortcuts, posted list, Hide/Unhide), projector list that shrinks to fit and hides at ENDED.
- Docs: ADR 0011, protocol §7.5 + changelog.

## Verified how
- `uv run pytest`: 86 passed, 4 skipped (Postgres); `ruff check` and `ruff format --check` clean. New: `tests/test_clarifications.py` (targeting, hide/unhide, 304 vs 200 on version, validation, permissions) and a Postgres restart test.
- `npm ci && npm run gen && npm run build` pass.
- NOT verified: the 4 Postgres tests (no Postgres in this sandbox, including the new restart test and migration 0003), anything in a browser, docker compose, prod.

## Not done
Edit, Preview display, markdown/math, paragraph zoom, Deletion tab, live refresh of the admin list for a second admin.

## Decisions made
- ADR 0011.

## Next steps
1. Push, run `deploy.sh` (runs 0003). Post one to all rooms and one to a subset; check two displays and that Hide clears them within a few seconds.
2. Then: Edit clarification, Preview display, per-room delete.

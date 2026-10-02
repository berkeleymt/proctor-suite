# 2026-10-02: Claude (chat session): Slice 12, branding from config, projector full screen, super-admin page, domain setup

**Phase item:** Phase 1 follow-ups (PM list of 4)
**Directories touched:** `server/{app,alembic,tests,pyproject.toml,uv.lock}`, `contracts/openapi.json`, `web/{index.html,public,src}`, `infra/`, `docs/`, `README.md`
**PR / commits:** none; uncommitted (patch). Started from `27cf26b`.

## Done
1. Name and icon are config, not code: `APP_NAME` / `APP_ICON` (`infra/.env`, `.env.example`) -> `GET /api/brand` -> tab title (`<page> · <name>`), tab icon, login page (icon above name, centered). Placeholder `web/public/logo.svg`.
2. "Open display window": window sized to the screen, display goes full screen at once; if the browser refuses (it wants a click in that window), the next click/key does it, with a small hint. A display sign-in click also does it.
3. Super-admin page `/super`: Google sign-in + email allow-list, edit name, icon, proctor and admin passwords (Show / Change…, optional log-out of old sessions), add/remove super-admins. Protocol 0.9.0, migration 0007.
4. `docs/setup-domain-and-google.md`: what to give the DNS owner (A record, IP, Elastic IP check) and the Google Cloud steps.

## Verified how
- `uv run pytest`: 105 passed against a throwaway Postgres (migrations 0001-0007); `ruff check` / `ruff format` clean; `npm run gen` and `npm run build` pass.
- New tests: `tests/test_super.py` (brand, login rules, password change + log-out-old, validation, super-admin list; Google's token check is faked), Postgres restart test for settings and super-admins. A test caught a blank-name bug (whitespace-only name would have blanked the site name); fixed in the model.
- NOT verified: anything in a browser; the real Google button and token (needs a Client ID); full screen on the popup (browser behavior differs); compose `up` with the new env vars; Caddy with the real domain.

## Not done
Logo upload, "reset to .env", audit log, password hashing, `/auth/super-login` rate limit (see ADR 0014).

## Decisions made
- ADR 0014. Notable: saved values override `.env` from then on; passwords stay plain text so "Show" works; `SUPER_ADMIN_EMAILS` can't be removed on the page; you can't remove yourself; compose requires `APP_NAME`.

## Next steps
1. Before deploying: add `APP_NAME` (and `APP_ICON`) to prod `infra/.env`, else compose refuses to start. Then DNS and Google per `docs/setup-domain-and-google.md`.
2. In a browser: `/super` sign-in, change a password with and without the log-out box, add and remove a super-admin from two accounts; the tab title and icon on every page; "Open display window" on a real projector.
3. Then the bathroom log and roster slice.

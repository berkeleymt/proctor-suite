# 2026-10-03: Claude: admin timer buttons that stay put, floating bulk bar, layout tests

**Ticket / phase item:** PM request (Timers buttons resize and move each other; Reset disappears)
**Directories touched:** `web/`, `.github/workflows/`, `docs/`
**PR / commits:** not committed yet (bundled with the ADR 0019 work)

## Done
- Every Timers row: main action · +5 min · Reset · Edit… · Delete…, always, same places. Unavailable buttons grey out; clicking one shows why in a note at the bottom. [ADR 0020](../../adr/0020-admin-timer-buttons-fixed-slots.md)
- Bulk bar floats over the table while rooms are ticked, same buttons and look as a row, ✕ clears the ticks.
- Shared `components/ActionBar.tsx` + `--act-*` tokens in `styles.css`; rules in `screens/adminActions.ts`.
- Tests: `vitest.workspace.ts` with `unit` (jsdom) and `layout` (headless Chromium via Playwright). New: `admin-actions.test.ts` (16), `admin-page.test.tsx` (9), `layout.browser.test.tsx` (10). CI installs Chromium before `npm test`.

## Verified how
- `npm test`: 35 pass (the other session's `display.test.tsx` was being rewritten at the time and wasn't in the run). Layout project alone ~7–10 s.
- Mutation check: removing the main button's width reserve fails 4 tests; making the bulk bar non-floating fails 1.
- Screenshots from headless Chromium at 1440 px: rows line up in all five states; bulk bar floats over the header; the note appears at the bottom.
- `tsc` clean for these files.

## Not done / blocked
- [?] Not checked on a real phone or against the live server; the page was rendered with fake live data.
- The proctor page's Start/Pause button was not changed (it already is a single slot) and has no layout test yet.

## Decisions made (link ADRs in `docs/adr/` if any)
- ADR 0020.

## Next steps for whoever picks this up
- After deploy, walk one room through every state on prod with the bulk bar open.
- The Bathroom and Roster bulk bars (`.bulk`) still push the page down; move them to `ActionBar` + the floating bar if wanted.

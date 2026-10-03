# 0020: Admin timer buttons are fixed slots; the bulk bar floats

**Date:** 2026-10-03 · **Decided by:** Forrest (PM). Changes the Timers row and bulk-bar layout from ADR 0010.

## Decisions
- **Every room row shows the same five buttons in the same places:** main action · +5 min · Reset · Edit… · Delete…. The main button is the timer's next step (Allow start → Start → Pause → Resume → "Time's up") and is always as wide as its longest label.
- **Unavailable means greyed out, never hidden.** Clicking a greyed-out button shows a short note at the bottom of the screen saying why ("Pause first. Only paused or finished rooms can be reset."). The rules are the server's (protocol §5.4, reset only from PAUSED/ENDED, no delete while a timer is in progress), kept in one file, `web/src/screens/adminActions.ts`.
- **The bulk bar floats** over the top of the table while rooms are ticked (it no longer pushes the table down), with the same buttons, groups and look as a row: timer actions | +5 min, Reset | Edit…, Delete… and ✕ to clear the ticks. Its buttons never come and go either; they grey out when none of the ticked rooms can do them.
- **One design language:** `components/ActionBar.tsx` draws both, styled by the `--act-*` tokens in `styles.css`. Restyle there, not per screen.
- Status pills, the Remaining column, and the "×2" device count also keep a fixed width, so no column resizes when timers change state.

## How it stays this way
- `npm test` runs two projects. `unit` (jsdom, fast): the rules table in `admin-actions.test.ts` and the real page in `admin-page.test.tsx`. `layout` (headless Chromium, ~10 s): `layout.browser.test.tsx` measures that no button or column moves when rooms change state, when rooms are ticked, or when a note appears, and that nothing wraps at 768–1280 px.
- If a rule really changes, update the table in `admin-actions.test.ts` and write a new ADR.

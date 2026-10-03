# Design principles (keep in mind for every screen)

Source: PM direction, 2026-10-01 (consistency added the same day). The prototype works and looks fine; this is the bar for polish as features land. **Not a priority while features are still missing**, but do not build against it: obvious fixes are welcome, rewrites are not. Revisit in full before the Oct 31 dress rehearsal (polish pass owned by Forrest).

0. **Consistent.** The same thing always looks, sits, and behaves the same way, on every screen. One connection light, always at the right of the header. One dialog layout (title, short plain sentence, Cancel then the main button on the right). One way to confirm (Shift skips), one danger color for destructive actions, one grey ring for "not there". Deleting is always soft: the item moves behind "Show deleted (n)" on the same screen, with Restore and a confirmed, red Empty that removes it for good. A new element reuses an existing component (`components/ui.tsx`, `FitText.tsx`) before it invents a new one. Consistency is what makes it intentional and learnable: learn one screen, know them all.
1. **Intentional.** Every element, color, animation, and word is there for a reason. If you can't say what it's for, remove it. No generic "vibe-coded" template look: pick a type scale, a palette, and spacing once, and use them everywhere.
2. **Instantly obvious.** An admin or proctor should know what to do without a guide. One clear primary action per screen, labels that say what will happen, state that is visible at a glance (is it started? is it connected? is this my room?). Test it: hand it to someone new, say nothing, watch.
3. **Conversational and human.** Plain words, the way a helpful person would say it. "Is this your room?" not "Confirm room assignment". Errors say what happened and what to do next, never codes or blame. No filler, no exclamation marks, no robotic phrasing.
4. **Smooth.** Motion explains change (a room appearing, a sheet opening, a timer turning amber), is short (150-300 ms), never blocks input, and is off under `prefers-reduced-motion`. Nothing jumps, flashes, or shifts layout under the user's finger.
5. **Well-formed.** Consistent alignment, spacing, and states (hover, focus, disabled, loading, empty, error) for every control. Works on a phone held in one hand, a laptop, and a projector across a room. Keyboard and screen-reader usable.
6. **Calm when it matters.** The display and proctor screens are used under stress or in front of students. Big, quiet, unambiguous; risky actions ask once, clearly, and say what will happen to students.

## Rules pinned by tests

A test fails if one of these breaks. Change the rule on purpose (new ADR), not by accident.

| Rule | Test |
|---|---|
| Timers rows always show the same five buttons in the same places; unavailable = greyed out with a reason, never hidden ([ADR 0020](adr/0020-admin-timer-buttons-fixed-slots.md)) | `web/src/test/admin-actions.test.ts`, `admin-page.test.tsx` |
| Nothing on the Timers page moves or resizes when timers change state, rooms are ticked, or a note appears; buttons never wrap | `web/src/test/layout.browser.test.tsx` (real browser) |
| Row buttons and the bulk bar share one look (`ActionBar`, `--act-*` tokens) | `layout.browser.test.tsx` ("same button size") |
| The projector display has no controls ([ADR 0019](adr/0019-display-sizes-on-proctor-page.md)) | `web/src/test/display.test.tsx` |

Applies to: `web/` screens, copy, empty and error states, the proctor guide, and the runbook's screenshots. Skills `/apple-design` and `/animate` (.skill files) are the reference for motion and feel.

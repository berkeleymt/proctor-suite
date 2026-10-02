# Design principles (keep in mind for every screen)

Source: PM direction, 2026-10-01. The prototype works and looks fine; this is the bar for polish as features land. **Not a priority while features are still missing**, but do not build against it: obvious fixes are welcome, rewrites are not. Revisit in full before the Oct 31 dress rehearsal (polish pass owned by Forrest).

1. **Intentional.** Every element, color, animation, and word is there for a reason. If you can't say what it's for, remove it. No generic "vibe-coded" template look: pick a type scale, a palette, and spacing once, and use them everywhere.
2. **Instantly obvious.** An admin or proctor should know what to do without a guide. One clear primary action per screen, labels that say what will happen, state that is visible at a glance (is it started? is it connected? is this my room?). Test it: hand it to someone new, say nothing, watch.
3. **Conversational and human.** Plain words, the way a helpful person would say it. "Is this your room?" not "Confirm room assignment". Errors say what happened and what to do next, never codes or blame. No filler, no exclamation marks, no robotic phrasing.
4. **Smooth.** Motion explains change (a room appearing, a sheet opening, a timer turning amber), is short (150-300 ms), never blocks input, and is off under `prefers-reduced-motion`. Nothing jumps, flashes, or shifts layout under the user's finger.
5. **Well-formed.** Consistent alignment, spacing, and states (hover, focus, disabled, loading, empty, error) for every control. Works on a phone held in one hand, a laptop, and a projector across a room. Keyboard and screen-reader usable.
6. **Calm when it matters.** The display and proctor screens are used under stress or in front of students. Big, quiet, unambiguous; risky actions ask once, clearly, and say what will happen to students.

Applies to: `web/` screens, copy, empty and error states, the proctor guide, and the runbook's screenshots. Skills `/apple-design` and `/animate` (.skill files) are the reference for motion and feel.

# 0008: Projector display (fit + zoom), admin filters, bulk allow/edit

**Date:** 2026-10-01 · **Decided by:** PM (requirements), Claude (details). No contract change (protocol stays 0.3.0): bulk actions send one command or PATCH per room.

## Decision
- **Display fits, always.** `FitText` measures the timer at a reference size and scales it to the box (width and height), re-fitting on resize, zoom, and digit-count change. Zoom steps are 40-100% of "largest that fits" (default 80%), so A+ can never overflow. Zoom is remembered per device in `localStorage` (try/catch; works without it). Same component and buttons on the proctor screen's timer ("both timers"). Clarifications zoom (the wireframe's paragraph -/Auto/+) is **not built**: there are no clarifications yet; `useZoom(key)` is reusable for it.
- **Projector is light** regardless of OS theme (wireframe: light-theme projector page). Controls fade after 4 s without pointer/keyboard activity.
- **Proctor actions in one row:** Start/Pause/Resume, Open display window, Log out. Start is shown disabled until an admin allows it (wireframe). On phones the middle label shortens to "Display".
- **Admin filters:** a row under the header filters by room (text contains), test, status, duration. Select-all, and every bulk action, apply only to rooms that are visible and ticked. Changing a filter drops ticks on rooms that become hidden, so a hidden room can never be started by accident. Remaining time is not filterable (it changes every second).
- **Bulk:** Allow start (NOT_PERMITTED only), Start (permit then start where needed), +5 min, and Edit (duration and/or test label; blank = unchanged; duration skipped for started rooms). Up to 6 requests in flight. Edit uses its own sheet instead of the generic confirm.
- Added a **Test** column to the table so bulk label edits are visible and filterable.

## Not done
Display clarifications area and paragraph zoom, "Log" drawer fallback, projector mirror in the proctor panel, bathroom log, Reset, Hide, doc URL, "Show hidden".

# 2026-10-01: Claude (chat session): Slice 5, display + filters + bulk allow/edit + docs sweep

**Phase item:** Phase 1 frontend (display, control, admin) per wireframe
**Directories touched:** `web/src/{components/FitText.tsx,screens/{Admin,Display,Proctor}.tsx,styles.css}`, `docs/`, `README.md`. No server code changed.
**Commits:** none; uncommitted for a human to review and push. Started from `0168b5f` (pulled).

## Done
- Admin: bulk **Allow start** and bulk **Edit** (duration, test label); **filters** (room, test, status, duration) with "N of M" and Clear filters; select-all and bulk actions only on visible rows; **Test** column. ADR 0008.
- Display: new projector screen (light, `FitText` always fits, A-/A+ zoom, fading controls). Proctor: Start/Pause/Resume + Open display window + Log out on one row; timer zoom.
- Docs sweep: `specs.md` (progress banner), `development-plan.md` (status line, progress paragraph under the phase table), `STATUS.md`, `phase-1.md` (stale items fixed: duplicate Tests line, "events in memory only"), README, ADR 0008. `protocol.md`, `contracts/README.md`, `phase-0.md`, `CLAUDE.md` checked: still accurate (protocol unchanged at 0.3.0).

## Verified how
- `npm run build` passes (tsc + vite). Server untouched; its tests were not rerun this slice.
- NOT verified: anything in a real browser. In particular: `FitText` sizing on real layouts, the fading controls, filter + selection behavior, the bulk sheets, and the one-row proctor actions on a phone. Treat every web screen as `[?]`.

## Not done
Clarifications area and paragraph zoom on the display (no clarifications feature), projector mirror, bathroom log, Reset, Hide, doc URL, SSE.

## Next steps
1. Push, deploy, and open `/display` at several window sizes (and on a projector) first; this is the part most likely to need tweaks.
2. SSE + heartbeat, then Reset / Hide, then clarifications (protocol addition first).

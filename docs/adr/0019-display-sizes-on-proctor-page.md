# 0019: Projector sizes belong to the room, are set on the proctor page, and the display has no controls

**Date:** 2026-10-03 · **Decided by:** Forrest (PM). Changes ADR 0008 and the projector-layout part of ADR 0012. Protocol 0.13.0 (§7.9).

## Rule of thumb
Anything that changes what students see, or that another proctor needs to know, lives on the server as part of the room. Anything that only changes how one person's own screen looks stays in that browser. Audit on 2026-10-03: projector sizes were the only thing in the first group still kept per browser. "Is this your room?", full screen, admin filters and the device ID stay local on purpose. The size Auto picks also stays local, because it depends on that projector's screen.

## Decisions
- **The display has no buttons.** A−/A+ and ¶−/Auto/¶+ are in a "Projector display" box on the proctor page, each with a readout (timer as a percent; clarifications as "N of 8", or under Auto, the size it picked when known). Tests fail if a button or button group ever shows on the display.
- **One setting per room, on the server.** Every proctor page and display of the room shows the same. Not per projector: sizes are fractions of the screen, so one value suits any projector.
- **Only that room's proctor can change it.** Admins can't (PM: it would be clutter on the admin pages), and display pages can't either.
- **Last click wins, per field**, ordered by click time (`claimed_at_ms`) and then `command_id`. Absolute values ("set 90%"), never "one bigger", so two proctors clicking at once can't add up. Retries and late duplicates are no-ops, so no list of seen ids is needed. This is a separate endpoint (`PATCH /api/rooms/{id}/display`), not a timer command: the timer fold and its fixtures stay timer-only.
- **Offline first on the proctor's laptop.** A click is saved in the browser before it is sent, so a display window in the same browser follows at once even with the server down. A small queue sends it (one request in flight, backoff, same id on retry), and it survives a sign-out. This is the pattern the Phase 2 outbox will generalize.
- The proctor page's own timer is a fixed size.
- **Clarifications still disappear once time is up** (swire), and every surface now says so: the display footer, the proctor page, and the admin composer when picked rooms have finished.

## Consequences
- Contract change: `RoomSnapshot.display` (required), the new endpoint, three constants, migration 0010 (`rooms.display` jsonb, additive, so rollback is safe).
- The old browser-only keys (`zoom:display`, `clarsize:display`) are no longer read; a browser that had them falls back to the room's value.
- Found along the way: two proctor bathroom endpoints were never in `openapi.json`. A new test now fails if a server endpoint is missing from the contract; those two are listed as a known gap to fix.

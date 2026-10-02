# 0012: Clarification edit, per-room hide/delete, delete, Markdown + math, bigger projector text

**Date:** 2026-10-02 · **Decided by:** Claude (slice 9), for the PM to review. Extends ADR 0011.

## Decisions
- **Edit never replaces silently.** The server keeps every earlier wording (`previous`, max 10 edits, then 422). Displays show them crossed out and faded, then the new text. The admin list and the edit dialog's preview use the same component, so what the admin sees is what students see.
- **Hide asks first.** Hiding a published clarification opens a dialog that says students get no sign it was taken back and offers **Edit instead** (pre-filled with a "Retracted" note) as the main button. **Hide anyway** is still there. Unhide needs no question. Shift does *not* skip these dialogs (the hide question exists to prevent day-of confusion, and delete is irreversible).
- **Delete wipes the row** (admin, PM). *(Superseded by ADR 0013: delete is soft; only Empty wipes.)* Everywhere, or from one room (`?room_id=`). Deleting from the last targeted room wipes the row. Per-room delete on an "All rooms" post stores `removed_room_ids`, so rooms created later still get it.
- **Per-room hide** is `hidden_room_ids`, reversible, separate from global `hidden`.
- **Version counter is persisted** (`clar_counter`, migration 0004). Delete removes a row, so rebuilding the counter as `max(rev)` could step backwards after a restart and devices would ignore newer snapshots (`mergeRoom` keeps the higher version).
- **Room targeting is compact.** Quick picks: All rooms, All <building>, All <test>, Clear. They toggle and add up (All Evans + All Soda). Single rooms live in a searchable, scrollable "Pick rooms" popover. "Posted" shows one summary ("All rooms", "All Evans", "All rooms except 2", up to 3 names, or "37 rooms") plus a **Rooms** popover with each room's state (Showing / Hidden here / Deleted here) and its Hide / Delete buttons. The full truth is one click away; nothing is lost.
- **Markdown + math** with `markdown-it` (raw HTML off, so output is safe to inject) and KaTeX (`@vscode/markdown-it-katex`, `throwOnError: false`). Bundled by Vite with KaTeX's fonts, so nothing comes from a CDN (invariant 6). Cost: bundle is ~550 kB JS (186 kB gzip) plus font files. Trim fonts or code-split later if the offline cache needs it.
- **Projector layout.** With clarifications, the timer sits at the top (24% of the screen height, centered, still A−/A+ adjustable) and the text fills the rest, semibold. **Auto** picks the largest size that fits, up to 11% of screen height; **¶− / ¶+** set fixed steps (starting from the size Auto is showing) and are remembered per device. The ¶ controls fade with the A−/A+ ones and exist only on the display.
- **Google Doc embed** was never rendered by the display (only stored). Now, if the room has `doc_url` and the timer isn't ended, the display shows the timer and an iframe of the doc *instead of* the text list. Google "edit" links are turned into `/preview` links; "Publish to web" links get `?embedded=true`. The doc must be viewable without sign-in ("Anyone with the link") or students see a Google login page. This is the one place the event depends on something outside our server (invariant 6): the doc is optional, and the text path doesn't use it.

## Not built (not asked, or outside this slice)
Preview-display button (the composer has a live side-by-side preview instead), the Deletion tab, ¶ Auto/zoom on the proctor page, live refresh of the admin list for a second admin.

## Consequences
Protocol 0.7.0 (`PATCH` takes `{hidden, room_id?}` or `{body}`; new `DELETE`; new snapshot fields), migration 0004 (additive, so `--rollback` is safe).

# 2026-10-02: Claude (chat session): Slice 9, clarification edit / delete / markdown / projector layout

**Phase item:** Phase 1 stretch: clarifications follow-ups (PM list of 10 items)
**Directories touched:** `server/{app,alembic,tests}`, `contracts/openapi.json`, `web/{package*.json,src/*}`, `docs/`
**PR / commits:** none; uncommitted for a human to review and push. Started from `3c1c6ef`.

## Done (numbers are the PM's list)
1. Admin tabs restyled as a navbar (text tabs, bold + underline on the current one, wireframe `.wf-nav`).
2. Send to: All rooms, All <building>, All <test>, Clear. Single rooms in a searchable scrollable popover.
3. Posted list: one summary pill ("All rooms", "All Evans", "All rooms except 2", "37 rooms") + a **Rooms** popover with per-room state.
4. Projector: timer pinned top, clarifications fill the rest at timer-like weight, ¶− / Auto / ¶+ (display only).
5. Edit clarification: old wording stays, crossed out and faded, then the new one.
6. Markdown + KaTeX in the composer (live side-by-side preview), posted list, and display.
7. Hide asks first, with "Edit instead" (pre-filled retraction note) and "Hide anyway".
8. Delete (wipes the row; protocol 0.7.0, migration 0004).
9. Per-room hide and delete, from the Rooms popover, same dialogs.
10. Doc URL: the display now frames the doc instead of the text list.

## Verified how
- `uv run pytest`: 89 passed, 5 skipped (Postgres). With a throwaway Postgres (pgserver, real Alembic run through 0004): 94 passed, 0 skipped, including the new restart test (edit, per-room hide/delete, delete, version counter after restart).
- `ruff check` / `ruff format` clean. `npm run gen` (types regenerated) and `npm run build` pass.
- Node check of the Markdown renderer: bold, bullets, inline and display math render; `<script>`, `<img onerror>` and `javascript:` links come out as plain text; broken math shows a red error instead of throwing.
- NOT verified: anything in a browser (none in this sandbox). Layout, popovers, the crossed-out math, the projector at real sizes, and the Google Doc iframe (a real doc, Google's framing rules) are all unchecked. docker compose and prod not run.

## Not done
Preview-display button, Deletion tab, live refresh of the admin list for a second admin, font/bundle trimming.

## Decisions made
- ADR 0012. Notable: Shift does not skip the hide or delete dialogs; room quick-picks add up instead of replacing.

## Next steps
1. Push, `deploy.sh` (runs 0004). Open `/display` on a real projector size: post a short and a long clarification, edit one, post one with `$x^2$` and a bullet list; try ¶− / Auto / ¶+.
2. Set a room's doc link to a Google Doc shared "Anyone with the link" and check the display embeds it.
3. Check the Rooms popover with ~200 rooms (scroll, search).

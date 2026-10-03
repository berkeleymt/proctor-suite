# Admin and proctor guide

How to use each screen. For setup and deployment see the [README](../README.md).

Each surface has its own cookie, so to try two at once, use two browser profiles or a private window.

| Screen | Path | Who |
|---|---|---|
| Login | `/` | Everyone |
| Proctor | `/proctor` | One room's proctors |
| Display (projector) | `/display` | A room's projector |
| Admin | `/admin` | Event staff |
| Super-admin | `/super` | Technical leads |

## Timers (`/admin`)

**Quick try:** open `/admin` in one window and `/proctor` in another. Admin: **Allow start**. Proctor: **Start**.

**Rooms**
- **Add room** takes a name and a duration. The room appears in the login dropdown.
- **Edit…** changes the duration (only before the timer starts) and the test label.
- **⋯** has Edit (rename, duration, label, doc link) and Delete. Delete hides the room; restore it from **Show deleted**.

**Finding and acting on rooms**
- The filter row narrows the list by room text, test, status and duration.
- Tick rooms (the header box selects only the rooms currently shown) and use **Allow start / Start / +5 min / Edit…** on all of them. Hold **Shift** to skip the confirmation.
- Each row shows only the buttons that make sense for its timer state: Allow start, Start, Pause, Resume, Reset, +5 min.
- **Reset** works only on a paused or finished room and puts it back to *Not started*.
- **Pages open** shows whether a proctor page and a projector page are open for each room.

## Projector display (`/display`)

- Always light theme.
- **A−/A+** resize the timer. It always fits the window.
- Controls fade when idle.
- **Open display window** (on the proctor page) opens the projector view sized to the screen and goes full screen. If the browser wants a click first, click once in that window.

## Clarifications (`/admin/clarifications`)

1. Write Markdown (bullets, **bold**, `$x^2$` math) and watch the live preview beside it.
2. Choose **Send to**: All rooms, All *building*, All *test*, Clear (these add up), or **Pick rooms** for individual rooms.
3. Press **Post**.

A clarification shows under the timer on the target rooms' `/display` pages (the timer moves to the top; **¶−/Auto/¶+** resize the text) and disappears when time runs out.

In the posted list:
- **Edit** keeps the old text on the displays, crossed out, followed by the new text.
- **Hide** asks first. If you are retracting something, edit it instead. **Unhide** brings it back.
- **Delete…** removes it for good.
- **Rooms** shows where it went and lets you hide or delete it for one room only.

A room with a doc link shows that Google Doc (shared "Anyone with the link") instead of the text list.

## Bathroom log and roster

**Proctor (`/proctor`)**
- Type a student ID and press **Mark out**. Press **Returned** when they are back.
- Returned students stay in the same list under a **Back** divider, faded.
- If a roster is loaded, the student's name and school show under the ID field as you type, with a warning if the student belongs to another room.

**Admin Bathroom log (`/admin/bathroom`)** (admins don't record, they review)
- Filter by room, **Out now / Returned / All**, and search by ID or name.
- **Export CSV**.
- Tick records (or the header box) and **Delete…**, or **Delete all…**. Both ask you to type `DELETE`.
- Deleted records move behind **Show deleted** (Restore, or the red **Empty** to remove for good).

**Admin Roster (`/admin/roster`)**
- **Sync** pulls students from ContestDojo (token and event ID come from `.env`).
- Filter by room and see who is out.
- **Clear roster…** (type `DELETE`) wipes it after the event. Students are minors, so do this.

## Branding, passwords and super-admins (`/super`)

- `APP_NAME` and `APP_ICON` in `infra/.env` set the tab title, tab icon and login page. Nothing else hard-codes the name. The icon is a file in `web/public/` (like `/logo.svg`) or an https link.
- `/super` signs in with Google (an email in `SUPER_ADMIN_EMAILS`, or one added on the page).
- There you can change the name, icon, proctor password and admin password with no redeploy. Saved values win over `.env`.
- You can also manage who else is a super-admin.

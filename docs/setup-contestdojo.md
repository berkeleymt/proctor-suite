# Setting up the roster (ContestDojo)

Goal: typing a student ID (like `054A`) shows their name, school and room to proctors and admins, and the admin Bathroom log shows names. Do this **before the event**, not on the day. Nothing on the event day talks to ContestDojo.

## Path A: CSV (works today, no one else needed)

1. Log in to ContestDojo as an admin of the BMT entity and open the event (BMT, Nov 14).
2. Find the page that lists **students/registrations** for the event. Look for an **Export / Download CSV** button there. *(I could not see the ContestDojo site, so I can't say exactly where it is. If there is no export, select the table, paste it into Google Sheets or Excel, and download as CSV.)*
3. Make sure the file has a header row with:

   | Needed | Column names that work (any capitalisation) |
   |---|---|
   | **ID** (what a proctor types) | `ID`, `Student ID`, `Number`, `Student Number` |
   | **Name** | `Name`, or `First Name` + `Last Name` |
   | optional | `School` / `Organization`, `Team`, `Room`, `Contact` (or `Parent / Coach Contact`, `Email`) |

   **Which column is "054A"?** Our best guess is ContestDojo's per-student *number*. If your export has a team number and a letter in separate columns, add one column in the spreadsheet that joins them (e.g. `=A2&B2` gives `054A`). Check one real student against what proctors will actually be given.
4. **Room column:** use the same room names as the Timers page (`Evans 10`, not `Evans Hall 10`); the match ignores capitalisation. If rooms aren't assigned yet, leave it empty. The only things that need Room are the "assigned to Soda 306" warning for proctors and the room filter on the Roster tab.
5. In the app: **Admin → Roster → Import CSV…**, choose the file, **Import**. You'll see "Imported N students" and any skipped rows (no ID, duplicates).
6. Spot-check: open `/proctor` in a private window, sign in as a room, type a real student ID. A name should appear under the field within a second.

Re-import any time (even event morning): it **replaces** the roster, it doesn't merge. Bathroom records already logged pick up names right away.

## Path B: Sync from ContestDojo's API (optional; needs help from ContestDojo)

**Status (2026-10-02): waiting on the ContestDojo maintainers to guide us. This is the only open Phase 1 item.** Until then use Path A.

The API repo (`github.com/contestdojo/api`) is archived and has no public address or login flow in it. It authenticates with a **token that someone with ContestDojo's database access must create** (a document in their `api_tokens` collection, tied to an admin user). Your website login can't do this. So:

1. Ask ContestDojo's maintainers (the repo author is Oliver Ni) for: **the API's base URL**, **an API token for an admin account on the BMT entity**, and **the event ID** for BMT 2026. Also ask whether the API still runs (the repo was archived July 22, 2026).
2. Ask them (or run once with `curl -H "Authorization: Bearer TOKEN" BASE/events/EVENT_ID/students/`) for one example student, and check: is `number` the `054A`-style ID? What does `roomAssignments` look like?
3. On the server edit `~/proctor-suite/infra/.env`:

   ```
   CONTESTDOJO_API_URL=https://<their base url>
   CONTESTDOJO_API_TOKEN=<token>
   CONTESTDOJO_EVENT_ID=<event id>
   CONTESTDOJO_ROOM_KEY=<key inside roomAssignments, only if you want rooms from it>
   ```
   then `bash deploy.sh` (or `docker compose up -d app`). The **Sync** button appears on the Roster tab.
4. Press Sync, then do the same spot-check as step 6 above. If names or rooms look wrong, use Path A instead; nothing else changes.

## Privacy and cleanup

The roster holds names, schools and parent/coach contacts of students (minors). Only admins see contacts; proctors see name, school, team and room. After the event, wipe it with **Admin -> Roster -> Clear roster…** (type DELETE). If the page is unavailable, the fallback is:

```bash
cd ~/proctor-suite/infra
docker compose exec postgres psql -U proctor -d proctor -c "DELETE FROM roster_students;"
docker compose restart app
```
(also clear the bathroom log first with **Delete all…**, then **Show deleted → Empty all…**, if you don't want those kept).

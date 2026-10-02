# Setting up the roster (ContestDojo)

The roster is filled **only** by syncing from the ContestDojo API (CSV import was removed). Do it **before the event**; event day never talks to ContestDojo.

1. Open `/super` (super-admin login) -> **ContestDojo**. Paste the **API token** and the **Event ID** (BMT 2026: `KTzD91YfMfE9zDvaTKjL`), then **Save**. No `.env` change is needed.
   - Optional `.env` values: `CONTESTDOJO_API_URL` (default `https://api.contestdojo.com`) and `CONTESTDOJO_ROOM_KEY` (key inside `roomAssignments`, only if rooms should come from ContestDojo).
2. Admin -> **Roster** -> **Sync**. It reads `/students`, `/teams` and `/orgs` of the event and joins them (a student carries its `org` and `team` ids), and **imports every student returned**.
   - Student ID = ContestDojo `number` when set (e.g. `054A`); until numbers are assigned, the ContestDojo user id is used so nobody is dropped. Sync again once numbers exist: it **replaces** the roster.
   - School = org name (else the `school` custom field); team = team name.
3. Spot-check a real student in `/proctor`.

Privacy: the roster holds minors' names and emails. After the event use **Admin -> Roster -> Clear roster…** (type DELETE).

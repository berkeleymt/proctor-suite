# Setting up the roster (ContestDojo)

The roster is filled **only** by syncing from the ContestDojo API. Do it **before the event**; event day never talks to ContestDojo.

1. Put `CONTESTDOJO_API_TOKEN=<token>` and `CONTESTDOJO_EVENT_ID=<id>` (BMT 2026: `KTzD91YfMfE9zDvaTKjL`) in `~/proctor-suite/infra/.env`, then `bash deploy.sh`. Or set them on `/super` -> **ContestDojo** (a value saved there wins over `.env`, like the passwords, and needs no redeploy).
2. Admin -> **Roster** -> **Sync**. It reads `/students`, `/teams` and `/orgs` of the event, joins them, and **imports every student returned**.
   - Student ID = ContestDojo `number` when set (e.g. `054A`); until numbers are assigned, the ContestDojo user id is used so nobody is dropped. Sync again once numbers exist: it **replaces** the roster.
   - School = org name (else the `school` custom field); team = team name. ContestDojo has no rooms: select students on the Roster tab (search a team or school, tick the box) -> **Set room…**. Rooms survive later syncs (matched by email, else name).
3. Spot-check a real student in `/proctor`.

Privacy: the roster holds minors' names and emails. After the event use **Admin -> Roster -> Clear roster…** (type DELETE).

After Sync the Roster page reports what ContestDojo sent ("ContestDojo sent N students, T teams, O orgs"). If N is not what you expect, the event ID on `/super` is probably another event; it is not a bug in the import, which keeps every student returned.

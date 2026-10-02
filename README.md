# Proctor Suite

Agents: read `docs/CLAUDE.md`, `docs/status/STATUS.md`, and all other relevant `docs/*.md` files first.

## Run locally

```bash
cd infra
cp .env.example .env        # defaults work for local
docker compose up --build
```

Open <https://localhost> (accept the local certificate warning once).
Sign in as room `Evans 10` / `dev-room-pw`, or `Admin` / `dev-admin-pw`.

> Try it: open `/admin` in one window, `/proctor` in another (different browser profile or private window, since each surface has its own cookie). Admin: **Allow start**; proctor: **Start**. Admin: **Add room** (name + duration) adds a room that shows up in the login dropdown. **Edit…** changes a room's duration (only before it starts) and test label. Use the filter row (room text, test, status, duration) to narrow the list, tick rooms (or the header box, which selects only the rooms shown) and use **Allow start / Start / +5 min / Edit…** on them; hold Shift to skip the confirmation. Rows show the buttons that make sense for the timer's state (Allow start, Start, Pause, Resume, Reset, +5 min); **⋯** has Edit (rename, duration, label, doc link) and Delete (hides the room; restore from "Show deleted"). "Pages open" shows whether a proctor page and a projector page are open for each room. Reset only works on a paused or finished room and puts it back to Not started. `/display` is the projector view (always light; **A−/A+** resize the timer, which always fits the window; controls fade when idle).

> Clarifications: open **Clarifications** (tab at the top of `/admin`). Write Markdown (bullets, **bold**, `$x^2$` math) and watch the preview beside it. **Send to**: All rooms, All <building>, All <test>, Clear (they add up), or **Pick rooms** for single ones. **Post**. It shows under the timer on those rooms' `/display` pages (timer moves to the top; **¶−/Auto/¶+** on the display resize the text) and disappears when time runs out. In the posted list: **Edit** keeps the old text on the displays, crossed out, with the new text after it. **Hide** asks first (if you are retracting something, edit it instead); **Unhide** brings it back. **Delete…** wipes it for good. **Rooms** shows where it went and lets you hide or delete it for one room only. A room with a doc link shows that Google Doc (shared "Anyone with the link") instead of the text list.

> **Bathroom and roster.** A proctor types a student ID on `/proctor` and presses **Mark out**; **Returned** when they are back. Returned students stay in the same list under a **Back** divider, faded. If a roster is loaded, the name and school show under the ID field as you type (and a warning if the student belongs to another room). Admins don't record; they open **Bathroom log** (tab at the top of `/admin`): filter by room, **Out now / Returned / All**, search by ID or name, **Export CSV**. Tick records (or the header box) and **Delete…**, or **Delete all…**; both ask you to type DELETE. Deleted records move behind **Show deleted** (Restore, or red Empty to remove for good). **Roster** (next tab): **Import CSV…** (or **Sync** if ContestDojo is connected), filter by room, see who is out, and **Clear roster…** (type DELETE) wipes it after the event. Setup, including ContestDojo: [`docs/setup-contestdojo.md`](docs/setup-contestdojo.md).

> **Name, icon, passwords, super-admin.** `APP_NAME` and `APP_ICON` in `infra/.env` set the tab title, tab icon and login page (nothing else hard-codes the name; the icon is a file in `web/public/` like `/logo.svg`, or an https link). **Open display window** opens the projector view sized to the screen and goes full screen (if the browser wants a click first, click once in that window). `/super` is the super-admin page: sign in with Google (an email in `SUPER_ADMIN_EMAILS` or added on the page), change the name, icon, proctor and admin passwords (no redeploy; saved values win over `.env`) and manage who else is a super-admin. Setup for Google and for the `lemon.berkeley.mt` domain: [`docs/setup-domain-and-google.md`](docs/setup-domain-and-google.md).

Rooms and timers are saved in Postgres: `docker compose restart app` keeps everything (people just have to sign in again). To start fresh: `docker compose down -v`.

Server tests, including the real-Postgres ones: `cd server && TEST_DATABASE_URL=postgresql://user:pw@localhost:5432/dbname uv run pytest` (they drop and recreate the tables in that database, so point it at a throwaway one; without the variable they are skipped).

## Deploy to prod (AWS)

```bash
sudo su - ubuntu
nano ~/proctor-suite/infra/.env   # add ROOM_PASSWORD=... and ADMIN_PASSWORD=... (strong, not the dev ones), APP_NAME=..., APP_ICON=...; see .env.example
```

```bash
cd ~/proctor-suite/infra
bash deploy.sh              # pulls main, builds, runs DB migrations, restarts, checks health
# bash deploy.sh --rollback  if something is wrong
```

The first deploy of this version creates the database tables (Alembic) and loads the seed rooms once; after that rooms live in the database and `SEED_ROOMS` is ignored. Migrations are additive, so `--rollback` is safe.

Then check `https://lemon.berkeley.mt/healthz` returns `ok`, and open the site root.

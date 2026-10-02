# Proctor Suite

Agents: read `docs/CLAUDE.md` and `docs/status/STATUS.md` first.

## Run locally

```bash
cd infra
cp .env.example .env        # defaults work for local
docker compose up --build
```

Open <https://localhost> (accept the local certificate warning once).
Sign in as room `Evans 10` / `dev-room-pw`, or `Admin` / `dev-admin-pw`.

Try it: open `/admin` in one window, `/proctor` in another (different browser profile
or private window, since each surface has its own cookie). Admin: **Allow start**; proctor: **Start**. Admin: **Add room** (name + duration) adds a room that shows up in the login dropdown. **Edit…** changes a room's duration (only before it starts) and test label. Use the filter row (room text, test, status, duration) to narrow the list, tick rooms (or the header box, which selects only the rooms shown) and use **Allow start / Start / +5 min / Edit…** on them; hold Shift to skip the confirmation. Rows show the buttons that make sense for the timer's state (Allow start, Start, Pause, Resume, Reset, +5 min); **⋯** has Edit (rename, duration, label, doc link) and Delete (hides the room; restore from "Show deleted"). "Pages open" shows whether a proctor page and a projector page are open for each room. Reset only works on a paused or finished room and puts it back to Not started. `/display` is the projector view (always light; **A−/A+** resize the timer, which always fits the window; controls fade when idle).

Clarifications: open **Clarifications** (tab at the top of `/admin`), type text (a line starting with `- ` is a bullet), pick rooms with the chips (All rooms, Clear, All <building>, by test), **Post**. It appears under the timer on those rooms' `/display` pages and disappears when time runs out. **Hide** takes it off the projectors; **Unhide** brings it back.

Rooms and timers are saved in Postgres: `docker compose restart app` keeps everything (people just have to sign in again). To start fresh: `docker compose down -v`.

Server tests, including the real-Postgres ones: `cd server && TEST_DATABASE_URL=postgresql://user:pw@localhost:5432/dbname uv run pytest` (they drop and recreate the tables in that database, so point it at a throwaway one; without the variable they are skipped).

## Deploy to prod (AWS)

```bash
sudo su - ubuntu
nano ~/proctor-suite/infra/.env   # add ROOM_PASSWORD=... and ADMIN_PASSWORD=... (strong password, not the dev ones)
```

```bash
cd ~/proctor-suite/infra
bash deploy.sh              # pulls main, builds, runs DB migrations, restarts, checks health
# bash deploy.sh --rollback  if something is wrong
```

The first deploy of this version creates the database tables (Alembic) and loads the seed rooms once; after that rooms live in the database and `SEED_ROOMS` is ignored. Migrations are additive, so `--rollback` is safe.

Then check `https://52-33-41-153.sslip.io/healthz` returns `ok`, and open the site root.

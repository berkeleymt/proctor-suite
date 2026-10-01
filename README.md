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
or private window, since each surface has its own cookie). Admin: **Allow start**; proctor: **Start**. Admin: **Add room** (name + duration) adds a room that shows up in the login dropdown. **Edit…** changes a room's duration (only before it starts) and test label. Tick rooms (or the header box) for **Start selected** / **+5 min selected**; hold Shift to skip the confirmation.

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

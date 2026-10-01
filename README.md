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
or private window, since each surface has its own cookie). Admin: **Allow start**; proctor: **Start**. Admin: **Add room** (name + duration) adds a room that shows up in the login dropdown.

## Deploy to prod (AWS)

```bash
sudo su - ubuntu
nano ~/proctor-suite/infra/.env   # add ROOM_PASSWORD=... and ADMIN_PASSWORD=... (strong password, not the dev ones)
```

```bash
cd ~/proctor-suite/infra
bash deploy.sh              # pulls main, rebuilds web + server, restarts, checks health
# bash deploy.sh --rollback  if something is wrong
```

Then check `https://52-33-41-153.sslip.io/healthz` returns `ok`, and open the site root.

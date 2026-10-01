# Proctor Suite

Agents: read `docs/CLAUDE.md` and `docs/status/STATUS.md` first.

## Run locally

Full stack (matches prod; needs Docker):

```bash
cd infra
cp .env.example .env        # defaults work for local
docker compose up --build
```

Open <https://localhost> (accept the local certificate warning once).
Sign in as room `Evans 10` / `dev-room-pw`, or `Admin` / `dev-admin-pw`.

Fast dev loop (no Docker, no Postgres needed for slice 1):

```bash
cd server && ROOM_PASSWORD=dev-room-pw ADMIN_PASSWORD=dev-admin-pw uv run uvicorn app.main:app --reload
cd web && npm ci && npm run dev    # http://localhost:5173, proxies /api to :8000
```

Checks: `cd server && uv run pytest && uv run ruff check . && uv run ruff format --check .`,
`cd web && npm run build`.

Try it: open `/admin` in one window, `/proctor` in another (different browser profile
or private window, since each surface has its own cookie). Admin: **Allow start**; proctor: **Start**.

## Deploy to prod (AWS)

One-time, before the first deploy of slice 1: add the new secrets to the server's env file.

```bash
sudo su - ubuntu
nano ~/proctor-suite/infra/.env   # add ROOM_PASSWORD=... and ADMIN_PASSWORD=... (strong, not the dev ones)
```

Every deploy:

```bash
cd ~/proctor-suite/infra
bash deploy.sh              # pulls main, rebuilds web + server, restarts, checks health
# bash deploy.sh --rollback  if something is wrong
```

Then check `https://52-33-41-153.sslip.io/healthz` returns `ok`, and open the site root.

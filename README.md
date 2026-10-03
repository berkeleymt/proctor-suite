# Proctor Suite

[![CI](https://github.com/berkeleymt/proctor-suite/actions/workflows/ci.yml/badge.svg)](https://github.com/berkeleymt/proctor-suite/actions/workflows/ci.yml)

A web app that coordinates real-time room timers, test clarifications, and other proctoring tools during [Berkeley Math Tournament](https://berkeley.mt), used by 500+ volunteer proctors and test organizers across hundreds of rooms at once.

> **Agents:** read `docs/CLAUDE.md` (rules and invariants), `docs/status/STATUS.md` (where we are now), and any other relevant `docs/*.md` **before contributing or changing anything**.

## Main Pages

| Surface | What it does |
|---|---|
| **Proctor** (`/proctor`) | Start, pause and resume the room's timer once staff allow it. Log students out for the bathroom and back. |
| **Display** (`/display`) | Projector view with a timer that auto-fits any screen, plus posted clarifications underneath. |
| **Admin** (`/admin`) | Overview and manage timers, rooms, proctors, clarifications, bathroom logs, and student roster |
| **Super-admin** (`/super`) | Google sign-in to change site name, icon and passwords without redeploying. |

Full walkthrough of every screen: `docs/guide.md`

## Repository layout

```
server/      FastAPI app, Alembic migrations, tests
web/         React frontend (proctor, display, admin, super)
infra/       Docker Compose, Caddy, bootstrap.sh, deploy.sh
contracts/   openapi.json and timer-fixtures/ (the wire contract)
docs/        specs, protocol, plan, ADRs, status, setup guides
```

## Local testing

Requires Docker with Compose

```bash
git clone https://github.com/berkeleymt/proctor-suite.git
cd proctor-suite/infra
cp .env.example .env        # defaults work locally
docker compose up --build
```

Open <https://localhost> and accept the local certificate warning once.

| Sign in as | Password |
|---|---|
| Proctor | `dev-room-pw` |
| Admin | `dev-admin-pw` |

Rooms and timers live in Postgres, so `docker compose restart app` keeps everything (people just sign in again). To wipe all data and start fresh, use `docker compose down -v`.

## Server deployment (AWS)

Set up `infra/.env` (copy from `infra/.env.example`; never commit it).

Once changed on `/super`, saved passwords and API keys will override `.env`.

After you `git push`, CI (GitHub Actions) runs server lint + tests against Postgres, the web build, and `shellcheck` on `infra/*.sh`. CI fails if the generated contract files are stale.

## Deploy (AWS)

```bash
sudo su - ubuntu
nano ~/proctor-suite/infra/.env   # configure variables if needed
cd ~/proctor-suite/infra
bash deploy.sh                    # pulls main, builds, runs migrations, restarts, checks health
bash deploy.sh --rollback         # ONLY if something is wrong
```

Verify that `https://lemon.berkeley.mt/healthz` returns `ok`.

## Documentation

| Doc | Read it for |
|---|---|
| [`docs/CLAUDE.md`](docs/CLAUDE.md) | Rules, invariants, commands (agents start here) |
| [`docs/status/STATUS.md`](docs/status/STATUS.md) | Current state, blockers, next actions |
| [`docs/specs.md`](docs/specs.md) | What we are building |
| [`docs/development-plan.md`](docs/development-plan.md) | Architecture, invariants, schedule |
| [`docs/protocol.md`](docs/protocol.md) | Commands, snapshots, merge rules, version history |
| [`docs/admin-guide.md`](docs/guide.md) | How to use every screen |
| [`docs/design-principles.md`](docs/design-principles.md) | UI quality bar |
| [`docs/adr/`](docs/adr) | Decision records |
| [`docs/status/log/`](docs/status/log/) | Past agent sessions |

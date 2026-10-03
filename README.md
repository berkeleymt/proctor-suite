# Proctor Suite

[![CI](https://github.com/berkeleymt/proctor-suite/actions/workflows/ci.yml/badge.svg)](https://github.com/berkeleymt/proctor-suite/actions/workflows/ci.yml)

A web app that coordinates real-time room timers, test clarifications, and other proctoring tools during [Berkeley Math Tournament](https://berkeley.mt), used by 500+ volunteer proctors and test organizers across hundreds of rooms at once.

> **Agents:** read `docs/CLAUDE.md` (rules and invariants), `docs/status/STATUS.md` (where we are now), and any other relevant `docs/*.md` **before contributing or changing anything**.

## Main Pages

| Surface | What it does |
|---|---|
| **Proctor** ([`/proctor`](https://lemon.berkeley.mt/proctor)) | Start, pause and resume the room's timer once staff allow it. Log students out for the bathroom and back. |
| **Display** ([`/display`](https://lemon.berkeley.mt/display)) | Projector view with a timer that auto-fits any screen, plus posted clarifications underneath. |
| **Admin** ([`/admin`](https://lemon.berkeley.mt/admin)) | Overview and manage timers, rooms, proctors, clarifications, bathroom logs, and student roster |
| **Super-admin** ([`/super`](https://lemon.berkeley.mt/super)) | Google sign-in to change site name, icon and passwords without redeploying. |

## Repository layout

| Directory | Description |
| --- | --- |
| `server/` | FastAPI app, Alembic migrations, tests |
| `web/` | React frontend (proctor, display, admin, super) |
| `infra/` | Docker Compose, Caddy, bootstrap.sh, deploy.sh |
| `contracts/` | OpenAPI, timer-fixtures, and the wire contract |
| `docs/` | specs, protocol, plan, ADRs, status, setup guides |

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

Rooms and timers live in Postgres, so `docker compose restart app` keeps everything (people just need to sign in again). To wipe all data and start fresh, use `docker compose down -v`.

After you `git push`, CI (GitHub Actions) runs server lint + tests against Postgres, the web build, and `shellcheck` on `infra/*.sh`. CI will fail if the generated contract files are stale.

## Server deployment (AWS)

```bash
sudo su - ubuntu
cd ~/proctor-suite/infra
nano .env                         # configure based on .env.example, though super-admins can override them on /super
bash deploy.sh                    # pulls main, builds, runs migrations, restarts, checks health
bash deploy.sh --rollback         # revert latest deploy if something is wrong
```

Verify that [https://lemon.berkeley.mt/healthz](https://lemon.berkeley.mt/healthz) returns `ok`.

## Documentation

| Doc | Read it for |
|---|---|
| `docs/CLAUDE.md` | Rules, invariants, commands (agents start here) |
| `docs/status/STATUS.md` | Current state, blockers, next actions |
| `docs/specs.md` | What we are building |
| `docs/development-plan.md` | Architecture, invariants, schedule |
| `docs/protocol.md` | Commands, snapshots, merge rules, version history |
| `docs/guide.md` | How to use every screen |
| `docs/design-principles.md` | UI quality bar, pair with design `.skill` |
| `docs/adr/` | Decision records |
| `docs/status/log/` | Past agent sessions |

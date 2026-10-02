# Proctor Suite: instructions for agents

Real-time, offline-tolerant timer and proctoring app for Berkeley Math Tournament.

**First event: Sat Nov 14, 2026, ~200 rooms, ~800 devices.** Robustness beats features, every time.

- Read `specs.md` for *what* we're building.
- Read `development-plan.md` for *how*: architecture §3, invariants §4.1, schedule §6.
- Read `docs/protocol.md` for the contract (commands, snapshot, merge rules, constants) and `contracts/timer-fixtures/` for the timer behavior it pins down.
- Read `docs/status/STATUS.md` for *where we are right now*.

## Invariants (never violate; reviewers reject PRs that do)

1. No request from a room device reads Postgres. Reads come from the in-memory state.
2. Every client network loop allows one request in flight, has a timeout, and uses full-jitter exponential backoff.
3. Every mutating command carries a client-generated UUID and is idempotent on the server.
4. Remaining time is always derived from the event list and `serverNow()`. Never decrement a counter.
5. Commit to Postgres **before** updating memory and broadcasting.
6. Nothing outside our server is on the event-day critical path: no email, no OAuth, no CDN (bundle fonts and assets), no external APIs.
7. The display and control pages must render and keep time with the server down (Service Worker + IndexedDB).
8. No endpoint returns an unbounded list to a room device.
9. Exactly **one** server process (uvicorn `--workers 1`). Anything needing more requires a design review.
10. Schema changes only through reviewed Alembic migrations, run by `deploy.sh`, never automatically on app startup.

## Working rules

- Keep PRs small (≤ ~400 changed lines) and include tests. Stay inside the directories your ticket names.
- `docs/protocol.md` and `contracts/` are the contract. No approval gate (PM decision, ADR 0003), but every change must bump `PROTOCOL_VERSION`, add a changelog line in `docs/protocol.md` §14, re-export `contracts/openapi.json`, and say in the PR that it touches the contract.
- Don't write "optimization" changes without a benchmark that shows the problem first.
- **Feature freeze Nov 1, total freeze Nov 11.** After Nov 1, only bug fixes with a regression test.
- Record decisions as short ADRs in `docs/adr/`.

## Layout

| Path | What | Owner |
|---|---|---|
| `server/` | FastAPI app (Python 3.13, managed with `uv`) | Ian |
| `web/` | Frontend: display, control, staff (TS/React/Vite), from Phase 1 | Forrest |
| `infra/` | Docker Compose, Caddy, server scripts, AWS runbook | Forrest |
| `contracts/`, `docs/protocol.md` | Shared contract: protocol v0.1.0, `openapi.json`, timer fixtures | Both |
| `server/app/protocol/` | Pydantic wire models and constants (source of the OpenAPI file) | Both |

## Commands

Server, from `server/`:

- `uv sync`: install deps. uv picks Python 3.13 by itself; don't use the system `python`.
- `uv run pytest`: tests
- `uv run ruff check . && uv run ruff format --check .`: lint and format check
- `uv run python -m scripts.export_openapi`: regenerate `contracts/openapi.json` after editing `app/protocol/models.py` (a test fails if it's stale)
- `uv run uvicorn app.main:app --reload`: local dev server on :8000; needs Postgres for `/readyz`

Full stack locally, from `infra/`:

- `cp .env.example .env`, then run `docker compose up --build`
- Open <https://localhost>. Caddy uses a local certificate, so your browser will warn once.

## Conventions

- Shell scripts use LF line endings (enforced by `.gitattributes`) and must pass `shellcheck`.
- Python: async all the way down. No sync DB calls in request handlers.
- Pin versions: `uv.lock` and `package-lock.json` are committed. Docker images are pinned to a minor version.

## Design bar

UI work follows [`design-principles.md`](design-principles.md) (intentional, instantly obvious, conversational, smooth). Low priority until features land; fix obvious roughness, don't gold-plate.

## Progress tracking

Before you start, read `docs/status/README.md`, `docs/status/STATUS.md`, and the current `docs/status/phase-N.md`. When you finish, add a note to `docs/status/log/` (use `_TEMPLATE.md`) and update the checklist. Tick a box only with evidence; use `[?]` for anything you couldn't verify. Humans alone record approvals.

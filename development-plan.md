# Proctor Suite — Technical Development Plan

**Status:** Draft v2 for review · **Date:** 2026-09-26 · **Authors:** Forrest (with Claude) · **Reviewer:** Ian

Companion to [`specs.md`](specs.md). The spec says *what* we're building. This document covers *how*: the architecture, how we prove it's robust, how we get onto AWS, and how two developers working mostly through AI agents split the work.

**First event: BMT, Saturday November 14, 2026.** Internal goal: **a working prototype on a real server by Monday October 5.**

**Roles:** Ian leads the **engine** (server, timer and sync logic). Forrest leads **UI/UX, AWS, and testing** (§7.1).

**The main constraint:** the spring 2026 system (`berkeleymt/swire2`) failed on competition day. This system is **not based on it**. Its features and code are not carried over, and every feature here comes from `specs.md`. Section 1 only records *why it failed*, so we don't repeat the same architectural mistakes. Every decision below is judged first on whether it survives a bad day, and only after that on features or elegance.

### How to review this (Ian)

The decisions below need your sign-off before the contract sprint (§7.4). Reply to each with **agree**, **disagree**, or **discuss**. Everything else in the document follows from these.

| # | Decision | Where | Deviates from spec? |
|---|---|---|---|
| D1 | One server process; all live state in memory; Postgres only for writes, startup, and exports | §3.2 | No (spec is silent) |
| D2 | **Server-Sent Events + plain POST** instead of WebSockets | §3.6 | **Yes**, spec §11 says WebSockets |
| D3 | Timer stored as an **event list** with a deterministic offline merge (not last-write-wins) | §3.3–3.4 | Answers spec Q4 |
| D4 | Device clocks never trusted: server offset + monotonic clock | §3.5 | Answers spec Q5 |
| D5 | Frontend: TypeScript + React + Vite. The timer math exists in Python *and* TS, kept identical by shared test fixtures | §3.3, §3.9 | No (spec left it open) |
| D6 | Opaque session cookies that last the whole event (no JWTs, no email OTP) | §3.7 | No |
| D7 | Hosting: one EC2 instance + Docker Compose + Postgres on the same box (no ECS/RDS) | §5 | No |
| D8 | Answers to the spec's 10 open questions | §2.1 | Fills gaps |
| D9 | Spec changes: room-code login, staff "start on behalf", PMs export all, only staff end a test early, guarded test switch | §2.2 | **Yes**: small additions |
| D10 | Scope tiers: what must ship for Nov 14 vs. what can be cut | §2.3 | Yes: defers some spec features |
| D11 | Schedule, gates, and freeze dates | §6 | — |
| D12 | Work split and agent rules | §7 | — |

---

## 0. TL;DR

1. **The spring system didn't fail because 200 rooms is a lot of traffic. It failed because of its design.** Section 1 has the evidence. Its 200-room load test *failed* the night before the event, and that was with fewer devices than the real day.
2. **The server is allowed to crash, and the rooms shouldn't notice.** Every timer keeps running on its own device from data it already has. If the server or the WiFi goes down, clarifications and permissions pause, but no timer stops. This is the most important property of the design, and we test it automatically.
3. **The database is never read to serve a device.** Current state lives in memory in one server process. Clients get changes *pushed* to them over Server-Sent Events. Nobody polls every 2 seconds.
4. **The timer is a list of events** (start, pause, resume, adjust, end), not a counter that ticks down. Server and client compute the same answer from the same list. That makes offline merging deterministic and gives us the audit log for free.
5. **Device clocks are never trusted.** Clients measure their offset from the server clock and then count with a monotonic clock.
6. **AWS setup is deliberately boring:** one EC2 instance running Docker Compose (Caddy for HTTPS, the app, Postgres), with backups to S3. We resize it bigger for event day. It runs in a new AWS account Forrest creates (there's no BMT account yet), on a temporary `*.sslip.io` HTTPS address until `berkeley.mt` DNS is sorted out. A non-coder can follow the steps in Section 5, and we do this **this week**, not the week of the event.
7. **Robustness gets proven, not promised.** There's an automated chaos suite (kill the server, drop rooms offline, skew clocks, reconnect storms) and a load test at 2× event scale. Both must pass before we ship, plus a full human dress rehearsal on **Oct 31**.
8. **The timeline is ambitious on purpose.** Agents write code fast, so the core is scheduled for Oct 24, with extras pulled in whenever the gates are green. What agents *don't* speed up is verification: soak tests, rehearsals with real people, and freeze time. Those dates are fixed (§6).
9. **Work split:** Ian owns the *engine* (sync, timer, server core). Forrest owns *UI/UX, AWS, and testing*. They're separated by a contract we freeze this week.
10. **Feature freeze Nov 1, total freeze Nov 11.** No agent-written "optimizations" the night before.

---

## 1. Lessons from the spring system (architecture only; no features or code carried over)

I read `Desktop/Coding/contestproctor` (the swire2 repo, ~12k lines, last commit 2026-04-12). None of its features, UI, or code are used here. Its failures were about *architecture and process*, and those lessons apply no matter what features we build. **Please correct me with what you actually saw on the day.** These are inferences from the code and git history.

| # | What the code and history show | Why it matters |
|---|---|---|
| F1 | **The 200-room load test failed on 2026-04-12 at 00:04** (`scripts/reports/loadtest_20260412_000444.json`: `passed: false`, write p95 = 5.2s, p99 = 6.5s, read p99 = 3.5s). The later passing runs were at 50 and 100 rooms. | We went into the event knowing it didn't hold 200 rooms. The test also only simulated **200 devices**. Real day is ~400 proctors plus ~200 projectors plus staff, so **3–4× more**. |
| F2 | Each proctor page polls **every 2s** with `setInterval` and sends **4 requests per tick** (`/me/assignment`, `/me/room-state`, `/me/clarifications?limit=500`, `/me/restroom/events?limit=200`). There's no guard against overlapping requests and no backoff. | ~600 devices × 2 req/s ≈ **1,200+ req/s**, each re-sending full lists. When the server slows, `setInterval` keeps firing, so requests pile up and slow it further. That's a textbook **death spiral**. |
| F3 | Every poll reads Postgres through a sync SQLAlchemy engine inside `asyncio.to_thread`, with 2 uvicorn workers and a 10+20 connection pool per worker. | Throughput was capped by threads and database connections, not CPU. Once the pool is exhausted, requests queue and time out (`pool_timeout=10`), which feeds the retry storm. |
| F4 | A large **backend rewrite merged 2026-04-10**, plus "deep performance optimizations" PRs (many written by Devin) in the final 48 hours. | Big untested changes landed right before the event. The repo has **one test file** (`test_db_url.py`). Nothing tested timer logic, offline behavior, or concurrency. |
| F5 | JWTs expire after `JWT_EXPIRE_HOURS=12`. Admin login in production required **email OTP through an external service (Resend)**. | A device logged in the night before gets logged out mid-event. An email outage locks the admins out. Both are external or time-based failure modes on the critical path. |
| F6 | Schema was managed by a mix of Alembic migrations and "startup auto-compat", and migrations ran on container start. | A bad migration or schema drift kills startup, exactly when you need a fast restart. |
| F7 | The timer is re-rendered from polled `room_state`, and the client has no offline mode or service worker. | If the network blips or someone refreshes the page with WiFi down, the projector is blank or frozen. Any server problem shows up immediately in every room. |

**Design rules we take from this** (these go into `CLAUDE.md` as invariants agents must obey, see §4.1):
- Reads are served from memory and pushed; no polling loops against the database.
- Every network loop allows one request in flight, uses exponential backoff with jitter, and has a timeout.
- Nothing outside our own server is on the event-day critical path: no email, no third-party auth, no CDN.
- Sessions last through the event day.
- The display must keep working through server death.
- A load test at 2× the *real device count* is a hard gate.
- Freeze early.

---

## 2. Spec review: pushback and recommended answers

### 2.1 Recommended answers to the spec's open questions (§12)

| Q | Recommendation | Rationale |
|---|---|---|
| 1. Zones | **No Zone entity.** Give `Room` an optional `building` tag. A `TestSequence` is its own entity that many rooms *point to*, and each room keeps its own position in the sequence. | Rooms that share a sequence already act as the "zone". Changing the sequence changes it for all of them. Batch selection filters by building tag or current test. |
| 2. Proctor identity | When someone opens the control screen, ask for an optional free-text **"Your name(s)"** and attach it to every action from that device. No accounts. | Useful for incident review at almost no cost. Asking for a name doesn't slow login. |
| 3. Staff accounts | **Named accounts** for every Admin, PM, and TO, logging in with username and password. **No email OTP.** | The audit trail needs a person attached to each action, and there are only tens of accounts. Email OTP was an external dependency that could lock people out (F5). |
| 4. Offline conflicts | **An event log with a deterministic merge (§3.4), not last-write-wins.** Offline room actions are kept with their real timestamps. Admin actions are never overwritten. | Last-write-wins would throw away a real pause the room actually took. The event log keeps what happened in the room *and* guarantees admin actions land. It turns out to be simpler than it sounds (§3.4). |
| 5. Clock trust | **Never trust device wall clocks.** Measure offset from the server and count with the monotonic clock (§3.5). | School and volunteer laptops are often minutes off. This removes the question entirely. |
| 6. Message persistence | Messages **stay until cleared**, with an optional auto-expire set by the sender. They're cleared automatically when the room moves to the next test. | Predictable, and students never miss one. |
| 7. Room password | **Decided:** the **room code is the username**, and there's one password per event. Rotate it each event; only Admins can view or reset it. See 2.2(a). | No dropdown, so no misclicks. |
| 8. Pause guard | **A two-step modal:** tap Pause, then a full-screen "Pause Room 204's timer?" with a big Confirm button and an optional reason. **No hold-to-confirm.** | Hold-to-confirm behaves inconsistently on touchscreens and trackpads and is hard to explain to 400 volunteers. |
| 9. Per-room override | Yes. An adjustment affects **only the current TimerSession**, and the sequence's default durations never change. | Keeps the audit trail clean and avoids surprises in the next test. |
| 10. Batch selection | **Free-form multi-select** with filters (building, current test, state, "offline now") and a "select all filtered" button. Saved groups are an extra. | Covers every case in the spec without a new entity. |

### 2.2 Things I think are wrong or missing in the spec

**(a) Login: DECIDED.** The **room code is the username** (e.g. `EVANS60`), printed on the room packet, plus the event password. There's no dropdown. After login, the page shows the room name in huge text with "Is this your room?" to confirm. The staff dashboard shows how many devices are connected to each room, so a mistaken login is visible. *Action: update `specs.md` §5, which still says "room-name dropdown".*

**(b) Permissions can't reach an offline room. Fixed without adding anything to the proctor's screen.** Proctors get **no emergency button**, which keeps their screen as simple as possible. (This was only my earlier suggestion and was never in the spec, so the spec needs no change.) The gap is handled on the staff side and by procedure:
1. **Grant permission early.** The runbook has PMs grant permission to all rooms about 10 minutes before the "go". The permission is saved on each device, so a WiFi drop *after* that doesn't matter: the proctor can still press Start.
2. **Staff can start a room remotely** from the dashboard (Admin/PM only). If the room's devices are offline, they show the correct remaining time as soon as they reconnect, because the start was recorded on the server at the real moment.
3. **Last resort:** the paper and wall-clock fallback in §8.

**Spec addition:** add "Start timer on behalf of a room" to the Admin/PM row of the permission matrix.

**(c) "PM can export own rooms"** assumes rooms are assigned to PMs, which isn't in the data model. **Proposal:** for v1, PMs export everything. Only add PM-to-room assignment if you really want scoped views.

**(d) Can a proctor end a test early**, e.g. a room where every student finished? The spec says "stop" in places and "pause" in others. **Proposal:** proctors can only pause and resume, and ending early is a PM/Admin action. *(Decision needed.)*

**(e) What happens when "switch test" is used on a room that's still RUNNING?** **Proposal:** it's blocked unless the room is ENDED or NOT_PERMITTED, with a separate "force switch" that asks for confirmation and is logged.

**(f) Devices: DECIDED. Display = mostly computers; control = computers and phones.** The spec should say this and list supported browsers:

| Screen | Devices | Supported browsers | What this means for the design |
|---|---|---|---|
| Display (projector) | Laptops and desktops plugged into a projector | Latest 2 versions of Chrome, Edge, Firefox, Safari | Fullscreen, Screen Wake Lock, instant re-sync on wake. **The volunteer checklist must include "plug in the charger, and set the laptop not to sleep when the lid is closed"**, because Wake Lock can't stop a lid-close sleep. |
| Control (proctor) | Phones **and** laptops | Above, plus iOS Safari 16.4+ and Android Chrome | Phone-first layout with big touch targets. Phones kill background connections when the screen locks, so control **re-syncs the moment it becomes visible**, and the offline outbox survives the page being killed (IndexedDB). |
| Staff dashboard | Laptops (phones usable, not optimized) | Desktop browsers above | Dense table layout. Phones are fine for a quick check. |

**(g) Being offline-tolerant requires a Service Worker.** Without one, refreshing a page while WiFi is down gives a blank screen. This should be in the spec explicitly (§3.6).

**(h) Numbering bug:** the open questions refer to "Section 10", but Practice Mode is §10 and the open questions are §12.

### 2.3 Scope tiers

Robustness comes first, so features are tiered. **Tier 1 must ship. Tier 2 ships only if every robustness gate is green. Tier 3 waits until after the first event.**

| Tier 1 (the core) | Tier 2 (if gates green) | Tier 3 (later) |
|---|---|---|
| Event, rooms, room login, staff accounts | Test sequences with auto-advance | Saved room groups |
| Permission → per-room start → pause/resume → end | Free-text messages (reuses the clarification surface) | Editing a clarification's history view |
| Manual adjustments (Admin/PM) | Practice Mode (a separate practice event, §3.9) | Rich analytics, charts |
| Display and control screens with offline tolerance | Proctor names on actions | Multi-event dashboards |
| Clarifications (issue, edit, retract) | Filtered or partial CSV export | PM-to-room assignment |
| Bathroom log | | |
| Staff dashboard: every room's state and connectivity | | |
| Staff "start on behalf of room" (§2.2b) | | |
| Audit log and full CSV export | | |
| Admin "set current test" for selected rooms (a simple stand-in for sequences) | | |

Practice Mode is Tier 2 as a *product feature*, but the *rehearsal* it enables is required: the dress rehearsal (§6, Oct 31) happens either way, using a throwaway event.

---

## 3. Architecture

### 3.1 Big picture

```
  Room devices (~600)                      Staff (~30)
  ┌──────────────┐ ┌──────────────┐        ┌──────────────┐
  │ Display page │ │ Control page │        │ Staff app    │
  │ (projector)  │ │ (proctor)    │        │ Admin/PM/TO  │
  │ SW cache     │ │ SW cache     │        └──────┬───────┘
  │ local timer  │ │ outbox (IDB) │               │
  └──────┬───────┘ └──────┬───────┘               │
         │ SSE ▼  POST ▲  │                       │
         └────────────────┴───────────┬───────────┘
                                      │ HTTPS (HTTP/2)
                        ┌─────────────▼─────────────┐   EC2 instance
                        │ Caddy (TLS, reverse proxy)│   (Docker Compose)
                        └─────────────┬─────────────┘
                        ┌─────────────▼─────────────┐
                        │ FastAPI — ONE process     │
                        │  • in-memory RoomState    │
                        │  • per-room command lock  │
                        │  • SSE fan-out hub        │
                        └─────────────┬─────────────┘
                                      │ writes (+ load on startup)
                        ┌─────────────▼─────────────┐
                        │ Postgres (append-only     │── pg_dump every 5 min
                        │ events + current views)   │   (event day) → S3
                        └───────────────────────────┘
```

### 3.2 Server: one process, state in memory, events in Postgres

- **One uvicorn process, fully async.** 800 long-lived connections and a handful of writes per second is a light load for a single async Python process *if the database is off the read path*. Running one process means one in-memory copy of state: no cache to invalidate, no pub/sub, no locking across workers.
- **Handling a command** (e.g. "pause room 204"):
  1. Take that room's `asyncio.Lock`.
  2. Validate the command against current state.
  3. `INSERT` the event into `events` and update the `room_current` row in **one transaction**, then commit.
  4. Update in-memory state and bump the room's `version`.
  5. Broadcast the new room snapshot to every subscriber of that room and to staff.

  **The commit always happens before the broadcast**, so the server never tells a device something it could lose.
- **Startup:** load every room's current state from `room_current` (a few hundred rows) and start serving. **Target: under 5 seconds.** `docker compose` uses `restart: always`, so a crash means a short blip that clients ride out offline.
- **Reads never touch Postgres.** Snapshots come from memory. The database gets only writes, plus exports and admin config screens.
- Stack: FastAPI, Pydantic v2, SQLAlchemy 2.0 async with asyncpg, Alembic, and `uv` for the Python environment. `uv` pins Python and dependencies and avoids the Windows Python mix-ups documented in swire2's `AGENTS.md`.

### 3.3 Timer model: fold over events

Each `TimerSession` (one room running one test) has an ordered list of events:
`PERMIT`, `START(t)`, `PAUSE(t)`, `RESUME(t)`, `ADJUST(Δ, t)`, `END(t)`.
All times are **server-time**.

The snapshot sent to clients is the *folded* result:

```
status            ∈ {NOT_PERMITTED, PERMITTED, RUNNING, PAUSED, ENDED}
duration_ms       = scheduled duration
adjust_total_ms   = Σ Δ over ADJUST events
elapsed_banked_ms = Σ length of completed running intervals
running_since     = server-time of the last START/RESUME if RUNNING, else null

remaining(now) = duration_ms + adjust_total_ms − elapsed_banked_ms − (RUNNING ? now − running_since : 0)
```

`remaining ≤ 0` means ENDED (the server also writes an `END` event for exports). **Clients never "decrement a counter".** They recompute `remaining(serverNow())` every 250 ms, so they can't drift.

The fold is written **twice**, in Python (server) and TypeScript (client). Both are checked against the **same shared fixture files** (`contracts/timer-fixtures/*.json`: an event list, the expected snapshot, and the expected remaining time at several moments). Both CI jobs run every fixture. This is how we keep two implementations identical.

### 3.4 Offline commands and the merge rule (answers spec Q4)

- Every command a client sends carries a `command_id` (UUID), `device_id`, and `claimed_at` (the client's best estimate of server-time, from §3.5). **The server stores `command_id` as a unique key, so a retried command is applied only once.**
- **Offline, the control page keeps working.** Allowed offline: START (only if the room was already PERMITTED), PAUSE, RESUME, and bathroom out/in. Commands go into a persistent **outbox** in IndexedDB. The page shows its local projection: the last server snapshot, plus the outbox replayed through the same fold.
- **When the device reconnects**, it sends the outbox in order. The server inserts each event at its `claimed_at` time and refolds that session. To stop a bad clock from rewriting history, `claimed_at` must fall between the session's creation time and the server's receive time.
- **Merge rules.** They're deterministic and property-tested:
  1. Events are sorted by effective time.
  2. `ADJUST` events add up, so their order doesn't matter. An admin's adjustment always survives.
  3. A state transition that's invalid at its point in the sorted order is **kept in the log but marked `rejected`**, not applied. Example: a second PAUSE while already paused, which happens when two offline devices both paused.
  4. `END` and "switch test" are final. Room events claimed *after* them are rejected. Room events *before* them still count; a pause the room really took offline is honored.
  5. Rejected events show up in the dashboard's "conflicts" list, and as a toast on the device: "1 offline action was superseded by PM action."
- After reconnecting, the device **adopts the server snapshot**, which already includes its own events. Server and device agree by construction.

### 3.5 Clock sync (answers spec Q5)

- The client pings `/time`: it records `t0 = performance.now()`, gets back the server time, then records `t1`. Offset = `server_time + (t1−t0)/2`, anchored at `t1`. It keeps the sample with the **lowest round-trip time** out of the last 8, and re-syncs every 60 s and on every reconnect or wake.
- `serverNow() = anchorServerTime + (performance.now() − anchorPerf)`. The device's wall clock is never used, so a laptop set 7 minutes wrong still shows the right time.
- **Sleep and wake safety:** on some systems `performance.now()` stops counting during sleep. On `visibilitychange` or when the page resumes, the client compares how much `Date.now()` and `performance.now()` advanced. If they disagree by more than 2 s, it re-syncs. If it's offline, it falls back to the wall-clock delta and shows "time re-estimated".
- The EC2 server clock stays accurate through Amazon Time Sync (chrony), with no setup needed.

### 3.6 Transport and offline shell

- **Server-Sent Events (SSE), not WebSockets, for server-to-client updates. Normal `POST` requests for commands.** *(This pushes back on the spec's §11.)* Why SSE:
  - It's plain HTTP, so it passes through campus proxies more reliably.
  - The browser reconnects automatically.
  - Commands are ordinary requests with idempotency and retries.
  - Everything can be load-tested with plain HTTP tools.

  Each SSE message is a **full room snapshot plus `version`**. Snapshots are small (~2 KB), and sending the whole thing means a client can never end up in a half-updated state.
- **Heartbeat** every 15 s. If the client hears nothing for 35 s, it treats the connection as dead, reconnects with **full-jitter exponential backoff** (0 → 1, 2, 4 … up to 30 s), and shows the offline banner.
- **Fallback:** if SSE can't connect 3 times in a row, the client switches to `GET /rooms/{id}/snapshot?since_version=N` every 5 s ± jitter, which returns `304` when nothing changed. It's served from memory, so it's cheap.
- **Service Worker (vite-plugin-pwa / Workbox):** the display and control pages load from cache with no network. The last snapshot and the outbox live in IndexedDB. **Refreshing a projector with the server down still shows the running timer.**
- **All fonts and assets are bundled.** No CDN on event day.
- The display page requests a **Screen Wake Lock** and shows a subtle "last synced 12s ago" in a corner. It turns amber when offline and red once offline for more than 5 min.

### 3.7 Auth

- **Opaque random session tokens** stored in Postgres and cached in memory. We don't use JWTs. Room sessions stay valid **until the event is closed or the room password or code is rotated**, which fixes the 12-hour expiry problem (F5). Staff sessions last 24 h and can be revoked.
- **Sent as HttpOnly, Secure, SameSite=Lax cookies**, because the browser's `EventSource` can't send an Authorization header. Each surface gets its own cookie name (`display_sid`, `control_sid`, `staff_sid`) so one laptop can have several open. Every POST also requires an `X-Proctor-Client` header for CSRF protection.
- Passwords are hashed with argon2. Logins are rate-limited per IP and per room.

### 3.8 Data model (v1 tables)

`events_meta` (Event: id, name, is_practice, status, room_password_hash) · `rooms` (event_id, name, code, building, sequence_id, seq_pos) · `tests` · `test_sequences` + `sequence_items` · `timer_sessions` (room_id, test_id, duration_ms, created_at) · **`events`** (append-only: id, event_id, room_id, session_id, type, payload jsonb, actor_kind, actor_id, device_id, proctor_name, command_id UNIQUE, claimed_at, received_at, status applied|rejected) · `room_current` (the materialized fold for each room, updated in the same transaction) · `clarifications` + `clarification_versions` · `messages` · `bathroom_breaks` · `accounts` · `sessions` · `device_presence` (last heartbeat, clock offset, and outbox length reported by each device).

**The spec's AuditLog *is* the `events` table.** Clarifications, messages, and account changes also write rows there. Every CSV export is a query over it.

### 3.9 Frontend

- **TypeScript + React + Vite + Tailwind, one app with three entry routes:** `/display`, `/control`, `/staff`. It's a single build, with the display route kept especially small. React/TS is the stack agents are most reliable in, and typed code catches the class of bugs that 3,000-line HTML files hid in swire2.
- **`packages/sync-core`** holds the robustness logic in plain TypeScript with no UI dependencies: the clock, SSE and polling transport, outbox, fold, and connectivity state machine. It has a fake clock and fake network for tests. The screens are thin views on top of it.
- **API types are generated** from FastAPI's OpenAPI schema (`openapi-typescript`), so the front and back ends can't drift apart without CI failing.
- **Practice Mode (Tier 2):** every Event gets a mirrored practice event with `is_practice = true`. The login page has a "Practice" switch. A "simulate offline" button in practice mode lets proctors rehearse an outage.

### 3.10 Stack summary

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 async + asyncpg, Alembic, `sse-starlette` | Single uvicorn worker; `uv` + `uv.lock` |
| DB | Postgres 17 (Docker, same host) | Upgrade path: RDS if you want managed point-in-time recovery |
| Frontend | TS, React, Vite, Tailwind, vite-plugin-pwa, idb-keyval | `package-lock.json` committed |
| Proxy/TLS | Caddy 2 | Automatic Let's Encrypt; flushes SSE correctly |
| Tests | pytest + Hypothesis; Vitest; Playwright (chaos e2e); custom asyncio fleet simulator (load) | |
| CI/CD | GitHub Actions → GHCR image tagged by git SHA → manual `deploy.sh` on the server | Deploys are deliberate, never automatic |

---

## 4. Robustness engineering

### 4.1 Invariants (written into `CLAUDE.md`, and reviewers enforce them)

1. No request from a room device reads Postgres. Reads come from memory.
2. Every client network loop has one request in flight, a timeout, and full-jitter exponential backoff.
3. Every mutating command has a client UUID and is idempotent on the server.
4. Remaining time is always derived from events and `serverNow()`. It's never decremented.
5. Commit to the database, *then* update memory and broadcast.
6. Nothing outside our server is on the event-day critical path: no email, OAuth, CDN, or external APIs.
7. The display and control pages must render and keep time with the server down (Service Worker plus IndexedDB).
8. No endpoint returns an unbounded list to a room device.
9. There is exactly one server process. Anything that would need two processes needs a design review first.
10. Schema changes happen only through reviewed Alembic migrations. There's no "auto-compat" at startup. Migrations are a separate deploy step, not run by the app on boot.

### 4.2 Test layers

| Layer | What | Where it runs |
|---|---|---|
| Fold unit + property tests | Hypothesis generates random event sequences and checks invariants: remaining time never jumps except on ADJUST, it's the same after a replay, adjustments can be reordered, END is final | CI, every PR |
| Shared fixtures | The same `contracts/timer-fixtures/*.json` run in pytest **and** Vitest | CI, every PR |
| sync-core sim tests | Fake clock and network: drops, duplicates, reordering, 30-min outages | CI, every PR |
| API tests | Every command, permission check, idempotency, rejection path | CI, every PR |
| **Chaos e2e** (Playwright + Docker Compose) | Scenarios C1–C14 below, with real browsers | CI on `main`, nightly |
| **Load/soak** (fleet simulator) | 2× scale against a real EC2 instance | Manually, at each milestone and at T−7 days |
| Human rehearsal | Real volunteers, real devices, ideally real venue WiFi | Oct 31 dress rehearsal |

### 4.3 Chaos scenarios (each is an automated test with a pass/fail threshold)

| ID | Scenario | Pass condition |
|---|---|---|
| C1 | Server killed for 60 s mid-test | Every display keeps counting. They agree with the server within 1 s, within 10 s of restart |
| C2 | Room offline 10 min; pauses and resumes while offline | The server log shows the real pause interval. The room's other device matches within 5 s of reconnect |
| C3 | Admin adjusts +5 min while the room is offline | The room shows the adjustment within 5 s of reconnect |
| C4 | Admin ENDs the test while the room is offline and paused | Deterministic final state; the room's later actions are flagged `rejected` |
| C5 | Two devices in one room both offline, both issue PAUSE | One is applied, one is rejected, and both devices agree after reconnect |
| C6 | Device clock set 7 min wrong | The display matches the server within 1 s |
| C7 | Display refreshed while offline | The timer renders from cache and keeps counting |
| C8 | **Reconnect storm:** 1,600 clients reconnect at once after a restart | Nothing crashes; p99 is under 1 s within 30 s; all clients are current within 60 s |
| C9 | 2 s latency and 10 % packet loss | Every command is eventually applied exactly once; the UI stays responsive |
| C10 | Postgres unavailable for 30 s | Commands return "retry", clients queue them, nothing is lost |
| C11 | The same command delivered 3× | Applied once |
| C12 | Laptop sleeps for 5 min mid-test, then wakes | The display is correct within 2 s of waking |
| C13 | Session held for 16 h (simulated) | Still authenticated |
| C14 | Deploy/restart during a running test | Restart takes under 5 s; nothing visible breaks in rooms |

### 4.4 Load gates (on the actual instance type we'll use on event day)

- **Scale:** 400 rooms, **1,600 concurrent SSE devices** (2× the real ~800), 40 staff dashboards.
- **Bursts:** a global "go" to 400 rooms followed by 400 STARTs within 5 s; a clarification broadcast to 200 rooms; bathroom logging at 5/s. This runs as an **8-hour soak** with random device flapping.
- **Pass means:**
  - Command p99 under 500 ms.
  - A broadcast reaches every device in under 2 s.
  - CPU under 50 %.
  - No memory growth over 8 h.
  - Zero lost or duplicated commands (checked against the simulator's own log).
- **If it doesn't pass, we don't ship.** No exceptions this time (F1).

### 4.5 Observability

- `/healthz` (the process is alive) and `/readyz` (the database is reachable and state is loaded).
- Structured JSON logs, with Docker's log rotation turned on.
- A `/staff/system` page shows:
  - Connected devices per room (display and control).
  - Last heartbeat per device.
  - Clock offsets per device.
  - Outbox backlogs per device.
  - Rejected-event conflicts.
  - Event-loop lag and command latency.

  **During the event, this page is how PMs notice "Room 204's projector has been offline for 3 minutes" and send a runner.**
- An external uptime check (UptimeRobot, free tier) pings `/healthz` every minute and alerts by SMS or email. It's alerting only, not on the critical path.

---

## 5. AWS: the first path to a real server (step by step, for a non-coder)

**Shape:** 1 EC2 instance, Ubuntu 24.04, x86. It runs Docker Compose with `caddy`, `app`, and `postgres`. It has an Elastic IP (a fixed address), a DNS record like `proctor.berkeley.mt`, and backups to S3.
**Why not something fancier** (ECS/Fargate, load balancers, App Runner, Lightsail)?
- At our size, more moving parts means more ways to misconfigure things, and more consoles for a non-coder to learn.
- App Runner doesn't support long-lived streaming well.
- Lightsail's plans get *CPU-throttled* under sustained load, which is a trap on event day.
- A single well-tested box, plus clients that tolerate server death, is more robust *in practice* than a cluster nobody on the team fully understands.

### Phase 0 goal: by Tue Sep 29, `https://proctor.berkeley.mt/healthz` (or the temporary `sslip.io` address) returns `ok` from AWS

Before the console steps, the repo needs `infra/docker-compose.yml`, `infra/Caddyfile`, `infra/bootstrap.sh`, `infra/deploy.sh`, `infra/.env.example`, and a hello-world FastAPI app. Forrest owns `infra/` and Ian reviews it. The full click-by-click version of the steps below will live in `infra/README.md`.

**Before you start: whose account this is.** There's no BMT AWS account, so Forrest creates one. BMT plans to move all its tech into it eventually, so set it up to be **handed over later**, not tied to one person:
- Sign up with a **shared BMT address** (e.g. `tech@berkeley.mt` or a Google Group), not a personal email. Whoever controls that inbox controls the account, which makes future handoffs painless.
- Store the root password and MFA recovery codes in a shared password manager that two people can access.
- A personal card is fine for now. Billing can be moved to a BMT card later without rebuilding anything.
- **Pushback on "all BMT tech on the same server":** the same **AWS account** is a great idea (one bill, one login, shared backups). The same **server** is not. If another BMT app has a bad deploy or a traffic spike on Nov 14, proctoring goes down with it. Keep the proctoring server separate at least for event weekends. A second small instance costs about $15/month.
- *If "host it myself" meant running it on your own computer or home network instead of AWS: please don't for event day.* Home internet, power, and router are each a single point of failure, and you'd be at the venue, not home.

**Step 1: Account safety (15 min)**
1. Go to aws.amazon.com → **Create an AWS account**, using the shared email from above. Choose the free **Basic support** plan.
2. Turn on **MFA for the root user**: top-right account menu → Security credentials → Assign MFA → use an authenticator app.
3. Set up a **budget alert**: search "Budgets" → Create budget → Use a template → *Monthly cost budget* → $40 → your email. This protects against surprise bills.
4. Create a day-to-day admin login instead of using root: search "IAM Identity Center" → Enable → Users → Add user (one for each of you) → give it `AdministratorAccess` on the account. Use that login from now on.

**Step 2: Choose a region.** Top-right region menu → **US West (Oregon) us-west-2**. It's cheap, has every instance type, and is ~20 ms from Berkeley. Always check you're in this region; resources in the wrong one look like they've "disappeared".

**Step 3: Give the server permission to be managed from the browser (5 min)**
1. IAM → Roles → Create role → Trusted entity: **AWS service → EC2**.
2. Attach the policy **`AmazonSSMManagedInstanceCore`**, which enables the in-browser terminal. Name the role `proctor-ec2-role`.
   *(Later, in Step 9, we add S3 write access to this same role for backups.)*

**Step 4: Launch the server (10 min)**
EC2 → Instances → **Launch instances**:
- Name: `proctor-prod`
- AMI: **Ubuntu Server 24.04 LTS, 64-bit (x86)**
- Instance type: **t3.small** for development (~$15/mo). *We resize for the event (Step 11).*
- Key pair: **"Proceed without a key pair"**. We use the browser terminal, so there are no SSH keys to lose.
- Network settings → Edit → Create security group `proctor-sg`:
  - Allow **HTTPS (443)** from Anywhere.
  - Allow **HTTP (80)** from Anywhere. Caddy needs this to get the certificate.
  - **Remove the SSH (22) rule.**
- Storage: **30 GiB gp3**
- Advanced details → IAM instance profile: **`proctor-ec2-role`**
- Launch.

**Step 5: Give it a permanent address (3 min)**
EC2 → Elastic IPs → Allocate → Allocate. Select it → Actions → **Associate** → choose `proctor-prod`. Write down the IP.

**Step 6: Web address: temporary for now (DECIDED)**
We start on a free **`sslip.io`** address built from the IP. For example, IP `54.183.10.20` becomes `54-183-10-20.sslip.io`. `bootstrap.sh` works this out automatically, and Caddy gets a real HTTPS certificate for it. No DNS access is needed.
*Later:* whoever controls `berkeley.mt` DNS adds an A record `proctor → <Elastic IP>`. We then change one line in `infra/.env` and restart Caddy. **This must be done by the Oct 31 rehearsal**, so volunteers learn the real address.

**Step 7: Open the browser terminal and install everything (15 min)**
EC2 → Instances → select `proctor-prod` → **Connect** → **Session Manager** tab → Connect. If it isn't available yet, wait 5 minutes after launch. Then paste these lines one at a time:

```bash
sudo su - ubuntu
```
```bash
git config --global credential.helper store
```
```bash
git clone https://github.com/berkeleymt/proctor-suite.git
```
```bash
bash ~/proctor-suite/infra/bootstrap.sh
```

The repo is **private**, so `git clone` asks for a username and password:
- Username: your GitHub username.
- Password: a **fine-grained GitHub token**. Create it at GitHub → Settings → Developer settings → Fine-grained tokens, with owner `berkeleymt`, access to **only** `proctor-suite`, **Contents: read-only**, and an expiry of Dec 31, 2026.

The token is remembered on the server, so later deploys don't ask again.

`bootstrap.sh`:
- Installs Docker and adds swap.
- Creates `infra/.env` with a generated database password and the `sslip.io` address.
- Builds and starts everything.
- Waits until `/healthz` answers and prints the address.

Re-running it is safe.

**Step 8: Verify.** Open the printed `https://…sslip.io` address on a laptop **and** a phone. You should see a "running" page with a padlock, and `/healthz` should show `ok`.

**Step 9: Backups (10 min)**
1. S3 → Create bucket `bmt-proctor-backups-<random>`. Keep "Block all public access" ON.
2. Under **Management**, add a **lifecycle rule** that deletes objects after 90 days.
3. IAM → Roles → `proctor-ec2-role` → Add permissions → Create inline policy → S3 → `PutObject` on that bucket only.
4. In the browser terminal, run `~/proctor-suite/infra/install-backups.sh` (written in mid-October, once the app stores real data). It sets up a nightly `pg_dump` to S3; on event day, `event-mode on` switches it to every 5 min.
5. EC2 → Lifecycle Manager → create a **daily EBS snapshot** policy for `proctor-prod`, keeping 7.

**Step 10: Monitoring (5 min)**
- EC2 → select the instance → Actions → Monitor and troubleshoot → **Manage CloudWatch alarms** → create an alarm on *status check failed* with the action **Recover instance**. AWS will then auto-restart it on dead hardware.
- Sign up for UptimeRobot (free) and monitor `https://<address>/healthz` every 5 minutes (the free tier's minimum), with alerts to both of your phones.

**Step 11: Deploying new versions (routine)**
- CI tests every merge to `main`. **Nothing deploys automatically.**
- To deploy: open the browser terminal → `sudo su - ubuntu` → `bash ~/proctor-suite/infra/deploy.sh`. It pulls `main`, builds the image *on the server* (tagged with the commit), runs migrations, restarts, and checks health.
- To undo: `deploy.sh --rollback`, which rebuilds the previously deployed commit.
- *Later option:* build images in GitHub Actions and push them to GHCR, so deploys only pull. Worth doing only if on-server builds get slow.

**Step 12: Event-day sizing (the day before)**
1. EC2 → select the instance → Instance state → **Stop**.
2. Actions → Instance settings → **Change instance type** → **c7i.xlarge** (4 vCPU, not CPU-throttled, ~$0.18/hr).
3. Start it again. The Elastic IP keeps the address the same.
4. **Re-run the load test against it, then reset the data.** Resize back to t3.small after the event.

**Also build `proctor-staging`** from the same steps (with its own `sslip.io` address, later `staging.proctor.berkeley.mt`). Keep it **stopped when not in use**, which costs only storage. Rehearsals and load tests hit staging first, then prod before the event.

**Rough cost:** t3.small ≈ $15 + storage ≈ $3 + public IPv4 ≈ $4 + S3 < $1, so **≈ $22/month**. The event-day upsize adds a few dollars. Staging, stopped, ≈ $3/month.

**Rebuild drill (required):** in Phase 3, delete a staging server and rebuild it from scratch and the latest backup, timing it. **Target: under 20 minutes**, following only the written runbook.

---

## 6. Phases, milestones, and gates

**Target: BMT, Saturday Nov 14, 2026 (E).** Today is Sat Sep 26, which leaves **7 weeks**. We're deliberately aiming high: agents make *writing* code fast, so feature phases are short, and Tier 2 is in play as soon as gates are green.

**Agents don't speed up verification:**
- An 8-hour soak still takes 8 hours.
- Volunteers can only rehearse on weekends.
- Bugs found in rehearsal need days to fix and re-verify.

So the verification dates below are fixed even if features land early. The schedule holds under three conditions:
1. **Tier 1 first** (§2.3). Tier 2 items start only after their dependencies pass their gates. Anything unfinished by the Nov 1 feature freeze waits until after the event.
2. **The gates aren't negotiable.** If a gate slips, we cut features to recover the time, not tests.
3. **A paper and radio fallback is prepared for Nov 14 no matter what** (§8). The first real use of *any* new system should have a way out.

Each phase ends with a **gate**. We don't start the next phase's feature work until the current gate is green. Some phases overlap because the two devs work in parallel.

| Phase | Dates | Deliverables | Gate |
|---|---|---|---|
| **0: Foundations** | Sat Sep 26 – Tue Sep 29 | Contract sprint (§7.4): protocol doc, Pydantic models, generated TS types, first 20 timer fixtures, `CLAUDE.md` + invariants. Repo skeleton + CI. **AWS account + prod server live with HTTPS** (§5; `sslip.io` is fine until DNS exists). Deploy/rollback scripts. | `healthz` is green on AWS; CI is green; both devs have approved the contract |
| **1: Prototype** ⭐ | Wed Sep 30 – **Mon Oct 5** | Room-code login; permit → start → pause/resume → end; admin ± adjust; display and control screens syncing over SSE **on the real AWS server**; clock sync; bare staff dashboard (room list, grant permission, adjust). *Not in the prototype:* offline outbox, Service Worker, clarifications, bathroom log, exports. | **Oct 5 demo:** 3+ phones and laptops on one room plus the staff dashboard, all in sync on AWS. C1, C6, C11 pass |
| **2: Offline core** (Ian) | Oct 6 – Oct 18 | Outbox, merge rules, Service Worker, wake lock, fallback polling, presence/system page, staff "start on behalf" | **Must-pass chaos set green in CI:** C1, C2, C3, C4, C6, C7, C8, C11, C12, C13. The rest are should-pass. Fold property tests pass 10k cases. *(Forrest writes the Playwright chaos tests in parallel, from Oct 6.)* |
| **3: Surfaces** (Forrest, in parallel) | Oct 6 – Oct 24 | Clarifications (issue/edit/retract), bathroom log, full staff dashboard with batch select, "set current test", audit + CSV export, a proctor-facing one-page guide | Every Tier 1 item works end-to-end on staging |
| **3b: Hardening** | Oct 19 – Oct 30 | Fleet simulator; **load gate (§4.4) on c7i.xlarge**; 8 h soak; backup restore drill; rebuild drill; event-day runbook draft | Load gate passes; rebuild in under 20 min, done by **Forrest** following the runbook |
| **4: Dress rehearsal** | **Sat Oct 31** | ≥ 20 people, ≥ 40 devices, on the *actual device types* and (ideally) at the venue, with scripted chaos: pull the WiFi, kill the server mid-test, pause, adjust, clarify | No P0/P1 bugs open |
| **Feature freeze** | Sun Nov 1 | From here on, only bug fixes that come with a regression test | |
| **Mini-rehearsal** | Sat Nov 7 | Staff-only (Admins/PMs/TOs) run-through of the runbook on the frozen build, plus a second load test | Everyone on staff has used it |
| **Total freeze** | Wed Nov 11 | Nothing merges. Resize prod on Fri Nov 13 (§5 Step 12) | |
| **Event** | **Sat Nov 14** | Runbook (§8) | |

**Stretch goals if the Oct 5 prototype lands early:** pull clarifications into Phase 1, and start Practice Mode and messages in Phase 3.

**Decision point on Oct 24:** if the must-pass chaos set or the load gate isn't green by then, we **cut scope** (e.g. drop CSV filtering, keep bare export), and the Nov 14 plan uses the software for timers and display only, with clarifications by radio. We decide this on Oct 24, not on Nov 13.

---

## 7. Work split and agentic workflow

### 7.1 Roles

The split is along the line that matters most for robustness: **who owns correctness of the sync engine.**

| | **Ian: Engine** | **Forrest: UI/UX, AWS, testing** |
|---|---|---|
| Owns | `server/` core (commands, fold, event store, SSE hub, auth), `web/packages/sync-core`, `contracts/`, the fleet simulator (load-test tool), unit, property, and sim tests for the engine | `web/apps/*` screens (display, control, staff) and their UX; clarifications, bathroom, messages, and export screens; `infra/` + the AWS console; **Playwright end-to-end and chaos suite (C1–C14)**; running load tests and soaks; runbooks; practice mode; rehearsals |
| How work is checked | Ian must understand every line of the engine: agents write drafts and Ian signs off on them | Forrest checks work by *looking at it and clicking through*, plus the Playwright tests agents write. AWS is done through the console steps in §5. Ian reviews `infra/` and anything touching `sync-core`. |
| Sep 26–29 together | Contract sprint: protocol, schemas, fixtures, invariants | Same, plus AWS Phase 0 |

Owning testing means Forrest is the one who says whether a gate is green. That's deliberate: the person who didn't write the engine decides whether it has passed.

### 7.2 Repo layout (keeps the two people and their agents out of each other's files)

```
proctor-suite/
  CLAUDE.md                 # invariants, commands, conventions (read by every agent)
  specs.md, development-plan.md
  docs/adr/                 # one short file per decision (why SSE, why single process, …)
  docs/protocol.md          # the frozen contract (CODEOWNERS: both devs)
  contracts/timer-fixtures/ # shared JSON fixtures (CODEOWNERS: both devs)
  server/                   # FastAPI (Ian) — own CLAUDE.md
  web/packages/sync-core/   # (Ian)
  web/packages/api-types/   # generated from OpenAPI, never hand-edited
  web/apps/app/             # display, control, staff routes (Forrest)
  infra/                    # compose, Caddy, scripts (Forrest, reviewed by Ian)
  loadtest/                 # fleet simulator (Ian builds, Forrest runs)
  e2e/                      # Playwright chaos + flows (Forrest)
```

### 7.3 Rules for working with agents (lessons from F4)

1. **Tickets are ready for an agent.** Each GitHub issue lists: goal, the directories in scope, **acceptance tests**, the invariants involved, and what's out of scope. An agent never gets a vague "make it faster".
2. **One ticket = one PR ≤ ~400 changed lines, tests included.** Run parallel agents in separate git worktrees, one per ticket.
3. **`contracts/` and `docs/protocol.md` need both humans to approve** (CODEOWNERS plus branch protection). The contract is how you work in parallel without talking every hour, so agents can't quietly change it.
4. **CI must be green to merge:** lint, typecheck, pytest, Vitest, fixtures (both languages), OpenAPI types up to date, Playwright smoke tests. Chaos e2e runs on `main` nightly, and a failure blocks new feature merges the next day.
5. **Review:** every PR is reviewed by the *other* human plus an automated `/code-review`. Engine PRs get a line-by-line read by Ian, whoever's agent wrote them.
6. **No "optimization" PRs without a failing benchmark** showing the problem first.
7. **Decisions go in ADRs**, a few short paragraphs each, so the next agent (or next year's team) knows *why* things are the way they are.
8. **Freeze:** after **Nov 1**, only bug fixes with a regression test. After **Nov 11**, nothing, including "tiny" UI tweaks.

### 7.4 Contract sprint (together, Sep 26–29, one or two sessions)

1. Agree on §2 decisions and resolve §9 questions.
2. Write `docs/protocol.md`:
   - The command list, with payloads and every rejection reason.
   - The snapshot shape.
   - SSE message types.
   - Heartbeat and backoff constants.
3. Write the Pydantic models for (2), export OpenAPI, and generate TS types.
4. Hand-write the **first 20 timer fixtures** together. This forces agreement on edge cases *before* any agent writes code.
5. Write `CLAUDE.md` with the invariants from §4.1.

---

## 8. Event-day runbook (outline; the full version is written by Oct 30)

- **T−1 day:**
  - Resize to c7i.xlarge.
  - Load test, then reset data.
  - `event-mode on` (5-minute backups).
  - Print room codes for the room packets.
  - Verify UptimeRobot alerts reach two phones.
- **T−2 h:** every display and control device logs in; the staff system page shows all rooms green.
- **Roles during the event:**
  - **Ops lead** watches `/staff/system` and alerts; has the browser terminal ready.
  - **Dev on call** has a laptop with the repo and can deploy a rollback in 2 min.
  - PMs use the dashboard and radio.
- **Degraded modes, practiced in rehearsal:**
  1. *One room offline:* its timer keeps going. The PM radios clarifications to that room. Nothing else to do.
  2. *Server down:* every timer keeps going. Ops runs `deploy.sh --restart`. If it's still down after 5 min, restore to a new instance using the rebuild runbook. Clarifications go by radio until it's back.
  3. *Everything down (venue WiFi dead):* timers keep running locally. Rooms that were already permitted (permission goes out ~10 min before the "go", §2.2b) can start normally. For a room that never got permission, the PM radios "start now". The room uses the paper fallback, and staff press "start on behalf" once the network is back, so the record is correct. Bathroom logs queue locally and upload later.
  4. *Last resort:* each room packet has a paper sign-out sheet and the test end time written by the PM at start. The software should never be the only record.
- **No deploys during the event** except a rollback approved by the ops lead.

---

## 9. Questions for you (these change the plan)

**Resolved (Sep 26):**
- Event = BMT, Nov 14, 2026, with a prototype by Oct 5.
- An ambitious timeline is OK.
- No BMT AWS account, so Forrest creates one (§5).
- Temporary `sslip.io` address; `berkeley.mt` later.
- Room code = username.
- No emergency start on the proctor screen (§2.2b).
- Display = computers; control = computers and phones (§2.2f).
- Ian = engine; Forrest = UI/UX, AWS, testing.
- No features or code from swire2.

**Still open:**
1. **Ian's sign-off on D1–D12** (top of this document).
2. **Venue network for Nov 14:** campus WiFi (eduroam/CalVisitor with a captive portal?), and can we get into the venue for the Oct 31 rehearsal?
3. **Can proctors end a test early (§2.2d)?** The proposal is no: staff only.
4. **OK to add staff-side "start on behalf of room" (§2.2b)?**
5. **Who controls `berkeley.mt` DNS?** This isn't urgent, but it must be sorted by Oct 31.
6. **What did you see when the spring system died?** Optional; it would confirm which of F1–F7 mattered.

---

## 10. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Schedule slips into the freeze (7 weeks is tight) | **High** | High | Tier 1 only (§2.3); hard gates; **Oct 24 scope decision**; paper/radio fallback prepared regardless |
| AWS account is tied to one person, or only one person can operate it | Medium | High | Sign up with a shared BMT email; two people hold credentials; both do the rebuild drill; runbook written for a non-coder |
| Other BMT services later share the proctoring server | Medium | High | Same account is fine; **separate instance**, at least on event weekends (§5) |
| Venue WiFi blocks or buffers SSE | Medium | Medium | Automatic fallback to polling; test on the venue network at the Oct 31 rehearsal |
| Offline merge bug corrupts a timer | Medium | High | Shared fixtures, property tests, and C2–C5; rejected events are shown, never silently dropped |
| Agent-written code nobody understands | High | High | §7.3 rules; engine read line by line by Ian; small PRs |
| Proctor logs into the wrong room | Medium | High | Room codes, a big confirmation screen, device counts on the dashboard |
| Single EC2 instance fails | Very low | Medium | Clients tolerate server death; CloudWatch auto-recover; practiced rebuild in under 20 min; backups every 5 min |
| Phones lock mid-test and the control page loses connection | High | Low | Outbox in IndexedDB; instant re-sync on visibility; the display (a laptop) is what students watch, so the timer itself is unaffected |
| Rehearsal finds late bugs | Medium | High | Rehearsal Oct 31 leaves 10 days to fix; Nov 7 staff mini-rehearsal re-checks fixes |
| Laptop sleep or tab throttling freezes a projector | Medium | Medium | Wake Lock, instant re-sync on visibility, C12, a checklist item in volunteer training |

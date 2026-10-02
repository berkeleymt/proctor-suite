# Proctor Suite — Technical Specification (Draft v1)

> **Implementation progress (2026-10-01).** This spec says *what*; it is not edited as we build. Live status is in [`status/STATUS.md`](status/STATUS.md). Built so far (prototype, not browser-verified): room-name login (§5), projector display and proctor control screens (§5), timer permit/start/pause/resume and admin start-on-behalf and +5 min (§4), admin timers table with add/edit/filter/bulk actions, Postgres persistence of rooms and commands. Not started: bathroom log (§6), offline tolerance (§7), clarifications and messaging (§8), export (§9), practice mode (§10), super-admin. Scope ceiling for UI is `docs/wireframe.html` (ADR 0004). UI quality bar: [`design-principles.md`](design-principles.md).

## 1. Overview

Proctor Suite is a real-time, offline-tolerant event-day tool for running standardized testing across many simultaneous rooms. It coordinates timers, bathroom-break logging, clarifications, and admin/proctor-manager messaging across roughly 200 rooms and 400 volunteer proctors, run by a small number of Admins, Proctor Managers (PMs), and Test Organizers (TOs).

**Scale target:** ~200 rooms, ~400 proctors, tens of Admin/PM/TO accounts, per event. Built to be reused across different tests/events over multiple years.

**Core design tension:** the system must work on unreliable venue WiFi (offline-tolerant, client-side timer math) while still guaranteeing all logged-in devices for a room show the same state (server as source of truth when available). Section 7 covers this in detail, with open decisions flagged.

---

## 2. Roles & Permission Matrix

| Capability | Admin | Proctor Manager (PM) | Test Organizer (TO) | Proctor |
|---|---|---|---|---|
| Create/edit/delete rooms | ✅ | ❌ | ❌ | ❌ |
| Create/edit Admin/PM/TO accounts | ✅ | ❌ | ❌ | ❌ |
| Assign test sequence to room(s) | ✅ | ❌ | ❌ | ❌ |
| Switch active test for a room/batch/all | ✅ | ❌ | ❌ | ❌ |
| Grant "permission to start" to room(s) | ✅ | ✅ | ❌ | ❌ |
| Send global "go" signal | ✅ | ✅ | ❌ | ❌ |
| Start/pause/resume timer (own room) | — | — | — | ✅ (start only after permission granted) |
| Start timer on behalf of a room | ✅ | ✅ | ❌ | ❌ |
| End a test early | ✅ | ✅ | ❌ | ❌ (proctors cannot end early) |
| Manually adjust a running timer (+/- time) | ✅ | ✅ | ❌ | ❌ |
| Log bathroom break (ID + timestamp) | — | — | — | ✅ |
| Write/edit/retract clarifications | ❌ | ❌ | ✅ | ❌ (view only) |
| Send free-text message to students (room/batch/all) | ✅ | ✅ | ❌ | ❌ |
| View/export all records (CSV) | ✅ | ✅ (all rooms in v1; no PM-to-room assignment) | ✅ (own tests) | ❌ |
| Enter/exit Practice Mode | ✅ | ✅ | ✅ | ✅ (own room only) |

Notes:
- PM and TO sit at the same hierarchy level, split by function: **PM owns timers/start-permission**, **TO owns clarifications**.
- Proctors have no messaging capability to anyone in-app; all proctor coordination happens outside the system (radio/Discord), per your confirmation.
- All Admin/PM/TO actions should be attributable to an individual account (open question below on whether these are named or shared logins).

---

## 3. Core Entities (Data Model)

This is a first-pass ERD in prose form; will be finalized once open questions in Section 10 are resolved.

- **Event** — a top-level container (e.g., "Spring 2027 Tournament"). Everything below belongs to an Event, so historical events can be archived/exported and a fresh Event stood up next year without carrying over state.
- **Room** — belongs to an Event. Fields: room name (used as login username), shared password (or event-wide password — open question), assigned test sequence, current test pointer, current timer state, permission-to-start flag, connectivity/last-seen status.
- **Test** — a reusable definition: name, duration preset(s), ordered list of Clarifications, metadata. Tests can be reused across events/years.
- **TestSequence** — an ordered list of Tests assigned to a Room (or a Zone, pending Section 10.1).
- **TimerSession** — one instance of a Room running one Test. Fields: room_id, test_id, scheduled_duration, started_at, paused_intervals[], ended_at, manual_adjustments[] (each adjustment: amount, actor, timestamp, reason), status (not_started / running / paused / ended).
- **BathroomBreak** — room_id, student_id (free text, no account), time_out, time_in.
- **Clarification** — test_id, body text, issued_by (TO), issued_at, retracted_at (nullable), version/edit history.
- **Message** — free-text, issued_by (Admin/PM), target scope (room / batch of rooms / global), body, issued_at, expiry/clear behavior (open question 10.6).
- **Account** — Admin / PM / TO / Room, with role, credentials, and (for Admin/PM/TO) audit trail of actions.
- **AuditLog** — append-only record of every state-changing action (permission grants, test switches, manual timer adjustments, clarifications issued/retracted, messages sent) for full day-of and post-event traceability.

---

## 4. Timer State Machine

States per Room: `NOT_PERMITTED → PERMITTED → RUNNING ⇄ PAUSED → ENDED`

- **NOT_PERMITTED**: default state. Proctor sees room is not yet allowed to start; start control is disabled/hidden entirely (not just greyed out) to make accidental starts impossible.
- **PERMITTED**: Admin or PM has granted this room (individually or via batch) permission to start. Proctor now sees an enabled "Start" control.
- **RUNNING**: proctor has tapped Start (ideally after a global "go" signal, though start itself is always a per-room proctor action). Timer counts down; projector screen updates live.
- **PAUSED**: an intentional stop, e.g., a disruption. Given the "hard to do accidentally" requirement, pausing/stopping a running timer should require a deliberate confirmation gesture (e.g., press-and-hold, or a two-step "Stop → Confirm Stop" pattern) rather than a single tap. Exact interaction pattern is an open design decision — see Section 10.
- **ENDED**: timer reached zero or was manually ended. Room awaits next test in sequence (Admin-driven) or event close.

Manual time adjustments (Admins/PMs can add or remove time from a running timer per your answer in 9) are logged in `manual_adjustments[]` with actor, amount, and timestamp, and should be visibly reflected on both the control screen and the projector screen so students see accurate remaining time.

**Global go signal → per-room start:** a global/batch "go" signal from Admin/PM does not auto-start any room's timer; it simply signals "you may start now" to proctors in PERMITTED rooms, who then start individually at their own moment (per your Q12 answer: "purely per room after global signal is sent").

---

## 5. Two-Screen / Two-URL Design

- Two distinct URLs, same login screen (room-name dropdown + password) on both.
- **Screen A — Projector/Student view**: displays only the timer and any active clarification(s)/messages for the current test. No controls. Designed to be safely left visible to a room full of students.
- **Screen B — Proctor Control view**: start/stop/pause controls (with confirmation friction, see Section 4), bathroom break entry, current test/clarification status, connectivity indicator.
- Any device logged into a given room account on a given URL shows identical state — there is no "pairing" step beyond logging into the same room account; state sync is by room identity, not by device pairing. (This satisfies "no matter how many devices are logged in, same account + same page = always in sync.")
- Because a room can have multiple proctors, and any of them can log into Screen B and act, all actions still need an audit trail — but note that without personal proctor identity at login (Section 10.2), actions will be attributable to the *room*, not the individual proctor, unless that's resolved otherwise.

---

## 6. Bathroom Break Tracking

- Proctor enters a student ID (free text, no student account) when a student leaves.
- `time_out` recorded automatically on entry.
- `time_in` recorded automatically when proctor marks the student as returned.
- No further student data is captured — this is intentionally minimal per your Q10 answer.
- All bathroom break records are exportable per Section 9.

---

## 7. Offline Tolerance & Sync Design

**Principle:** the timer must keep working and stay usable even if a room's connectivity drops mid-test. The server is the ultimate source of truth *when reachable*; when it isn't, the device's local timer math becomes the temporary source of truth for that room, and reconciles once connectivity returns.

Proposed approach (to be finalized — see open questions 10.4–10.5):
1. Each RUNNING TimerSession has a server-recorded `started_at` timestamp (and pause/resume timestamps). Clients compute "time remaining" locally from these timestamps plus the device clock, so the UI keeps ticking smoothly even without a live connection.
2. State-changing actions (start, pause, resume, manual adjustment, bathroom break log) are queued locally if offline and pushed to the server once reconnected, tagged with client-side timestamps.
3. On reconnect, the client reconciles: if the server has a newer/conflicting state (e.g., an Admin remotely ended the test, or adjusted time, while the room was offline), the server's version should generally take precedence, since Admins/PMs need certainty their day-of interventions actually land — but locally-recorded events that don't conflict (e.g., a bathroom break logged while offline) should simply be merged in, not discarded.
4. Multiple devices on the same room (Section 5) reading server state should poll/subscribe (e.g., WebSocket with polling fallback) so they reflect changes within a couple seconds of reconnecting.
5. Connectivity status should be visibly indicated to the proctor (e.g., "offline — local timer running" banner) so they're never confused about which mode they're in.

This is flagged as an open design area — see Section 10 for the specific unresolved conflict-resolution and clock-drift questions.

---

## 8. Clarifications & Messaging

**Clarifications (Test Organizer-owned):**
- Written and tied to a specific Test (not a room), so all rooms currently running that test see the same clarification.
- Because different buildings/zones can run different tests simultaneously, clarifications only ever reach rooms currently on the matching test — never a blanket broadcast.
- TO has full control: can issue, edit, and retract clarifications after the fact. Every version change is timestamped and logged (Section 3, `Clarification.version/edit history`) for audit purposes.
- Clarifications appear on the projector/student screen automatically (per test-instance) — no proctor action needed to display them, since students should see them "at the earliest time possible."

**Messages (Admin/PM-owned, student-facing only):**
- Free text, sent by Admin or PM, targeted to one room, a batch, or globally.
- Appears on the projector/student screen (same surface as clarifications, but a distinct message type).
- There is no PM/Admin → proctor channel in-app; this is intentionally out of scope per your confirmation, with proctor-facing coordination handled outside the system.
- Persistence/expiry behavior (does a message stay until cleared, or auto-expire?) is an open question — see 10.6.

---

## 9. Data Export

All records should be exportable to CSV, at minimum:
- **TimerSession log** — one row per room/test session: start, pause/resume events, end, manual adjustments (with actor + reason), computed actual duration.
- **BathroomBreak log** — one row per break: room, student ID, time out, time in.
- **Clarification log** — one row per clarification issued/edited/retracted: test, body, actor, timestamp, version.
- **Message log** — one row per message sent: scope, body, actor, timestamp.
- **AuditLog export** — full combined action log across all of the above, for complete day-of traceability (per your "record everything" answer).

Exports should be filterable by Event, and ideally by room/test/date range, so an Admin can pull a subset without downloading the entire event's history.

---

## 10. Practice Mode

A first-class mode (not a hack) that lets any role rehearse the full flow — granting permission, starting/pausing timers, logging bathroom breaks, issuing clarifications and messages, going offline/reconnecting — without writing to real event data. Given your "handle all edge cases" goal, Practice Mode is also the intended venue for proctors to specifically rehearse:
- Disruption/pause-and-resume
- Manual timer adjustment scenarios
- Loss of connectivity mid-test and recovery
- Wrong test loaded / needing correction
- A clarification arriving mid-test

Practice Mode data should be clearly segregated from real event data (e.g., its own Event record flagged as `is_practice = true`) so it never contaminates exports.

---

## 11. Tech Stack (as specified)

- **Backend:** Python, FastAPI
- **Database:** PostgreSQL
- **Hosting:** AWS
- Real-time sync via **Server-Sent Events plus plain POST commands**, with a polling fallback for degraded networks (decision D2 in `development-plan.md`; replaces the earlier WebSockets idea). See `docs/protocol.md`.
- Client-side timer computation (Section 7) to tolerate offline periods; exact framework not yet specified.

---

## 12. Open Questions (intentionally left unresolved)

These need answers before the data model and sync logic can be finalized:

1. **Zone/Building grouping:** should there be an explicit Zone entity grouping rooms with a shared test sequence, or is each of the 200 rooms configured independently (even if many share an identical sequence)?
2. **Proctor identity:** since room login has no personal identity attached, is there any need to track which of the 400 volunteers physically staffed which room (for accountability/incident review), or is this intentionally out of scope?
3. **Admin/PM/TO account model:** are these individually named accounts (so actions log to a specific person), or can they be shared/generic role logins?
4. **Offline conflict resolution rule:** when a room reconnects after an outage, should the server's last-known state always override local state, or should locally-accumulated elapsed time be preserved/merged rather than overwritten? This determines whether we need a real merge algorithm or a simpler last-write-wins rule.
5. **Device clock trust:** is it acceptable to trust each device's local clock for elapsed-time math during an outage, or do we need to account for clock drift/incorrect device time?
6. **Message persistence:** do free-text student-facing messages stay on screen until manually cleared, auto-expire after a set duration, or display as a one-time popup/banner?
7. **Room password model:** confirmed as one shared password across all rooms with room-name-as-username — should this password be rotated per event, and who is authorized to view/reset it day-of?
8. **Pause/stop confirmation pattern:** what specific interaction should guard against accidental pause/stop — hold-to-confirm, a secondary "confirm" tap, typing the room name, or requiring PM override for certain actions?
9. **Test sequence customization scope:** "Admins can customize anything" for test sequences and timer presets — does this include per-room overrides mid-event (e.g., one room needs extra time due to a disruption), and if so, does that only affect that room's current TimerSession or its whole future sequence?
10. **Batch selection UX for room permissions/messages:** what's the intended grouping for "select a batch of rooms" — by building/zone (pending Q1), by test currently assigned, or a fully free-form multi-select with saved groups?

---

*This is a first-draft technical spec meant to converge the requirements gathered so far. Sections 7 and 12 in particular should be resolved before backend implementation begins, since they affect the core data model (Zone entity, Account model, TimerSession conflict resolution).*

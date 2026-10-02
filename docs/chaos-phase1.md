# Chaos tests for the Phase 1 gate (C1, C6, C11), run by hand

Source: `development-plan.md` §4.3. These three are the Phase 1 gate. There is no Playwright suite yet (Phase 2, Forrest, `web/e2e/`), so run them by hand on prod (or staging) once, record the result below, and Forrest calls the gate. Phase 1 has **no Service Worker and no offline outbox**, so during C1 **do not reload** any open page: an already-open page keeps counting, a reload would fail until the server is back (that is Phase 2 work, C7).

**Setup for all three:** one room running a long test (for example 180 min). Device A: laptop on `/display`. Device B: phone on `/proctor` for the same room. Device C: any other laptop on `/admin`.

## C1: server killed for 60 s

Pass: every display keeps counting; within 1 s of the server's time while it is down; within 10 s of restart they agree with the server.

1. Put A and B next to each other (or in one photo) so you can compare seconds.
2. `ssh` to the server: `cd ~/proctor-suite/infra && docker compose stop app`. Caddy stays up and answers 502.
3. Wait 60 s. A and B must keep counting and show the same seconds. (Admin and the connection light will go red; that is expected.)
4. `docker compose start app`. Within 10 s the lights go green again and A, B and C agree with each other.
5. Press Pause on B, then Resume: both still work (state came back from Postgres).

## C6: device clock 7 min wrong

Pass: the display matches the server (and a correct device) within 1 s.

1. On laptop A, turn off "set time automatically" and set the clock **7 min ahead**. Reload `/display` (the clock sync runs at load).
2. Put it next to a correctly set device on the same room. Seconds must match. Repeat with **7 min behind**.
3. Turn automatic time back on.

## C11: the same command delivered 3 times

Pass: applied once.

1. On C (`/admin`), open DevTools -> Network. Press **+5 min** on the room. Right-click the `commands` request -> Copy -> **Copy as cURL**.
2. Note the room's remaining time. Paste that cURL into a terminal **3 times** (or loop it). All three return success.
3. The timer must have moved by **exactly 5 min total**, not 10 or 20. (The command id is the same, so the server ignores repeats.)

## Results

| Date | Scenario | Who | Devices | Result | Notes |
|---|---|---|---|---|---|
| | C1 | | | | |
| | C6 | | | | |
| | C11 | | | | |

If one fails: don't patch around it. Write what you saw in `status/log/`, and the fix needs a regression test (server for C11, `web/src/api.ts` clock sync for C6, `useLive` reconnect for C1).

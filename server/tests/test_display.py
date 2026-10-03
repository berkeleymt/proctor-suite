"""Projector display sizes (0.13.0): one setting per room, set by that room's proctor only,
last click wins per field, retries are no-ops, and every device of the room gets it."""

import asyncio
import time
import uuid

from app.store import Setting, Store, display_from_db, display_to_db
from app.stream import frames
from tests.test_api import H, mk
from tests.test_bathroom import proctor
from tests.test_room_management import make_room, staff
from tests.test_stream import decode


def now() -> int:
    return int(time.time() * 1000)


def put(c, room_id, at=None, cid=None, **kw):
    body = {"command_id": cid or str(uuid.uuid4()), "claimed_at_ms": now() if at is None else at}
    return c.patch(f"/api/rooms/{room_id}/display", json={**body, **kw}, headers=H)


def screen(monkeypatch, room_id):
    c = mk(monkeypatch)
    body = {"room_id": room_id, "password": "room-pw", "surface": "display"}
    assert c.post("/api/auth/room-login", json=body, headers=H).status_code == 200
    return c


def test_defaults_then_proctor_sets_and_the_display_sees_it(monkeypatch):
    admin = staff(monkeypatch)
    rid = make_room(admin, "Disp A")["room_id"]
    p, d = proctor(monkeypatch, rid), screen(monkeypatch, rid)
    s0 = d.get(f"/api/rooms/{rid}/snapshot").json()
    assert s0["display"] == {
        "timer_zoom_pct": 80, "clar_size": "auto", "timer_zoom_at_ms": None, "clar_size_at_ms": None,
    }  # fmt: skip
    r = put(p, rid, timer_zoom_pct=60)
    assert r.status_code == 200, r.text
    s1 = d.get(f"/api/rooms/{rid}/snapshot").json()
    assert s1["display"]["timer_zoom_pct"] == 60 and s1["display"]["clar_size"] == "auto"
    assert s1["version"] > s0["version"] and s1["display"]["timer_zoom_at_ms"] is not None
    s2 = put(p, rid, clar_size=5).json()  # the other field is left alone
    assert (s2["display"]["timer_zoom_pct"], s2["display"]["clar_size"]) == (60, 5)
    s3 = put(p, rid, clar_size="auto").json()
    assert s3["display"]["clar_size"] == "auto" and s3["version"] > s2["version"]
    # the staff list carries it too (no admin control uses it, but the snapshot is one shape)
    row = next(x for x in admin.get("/api/staff/rooms").json()["rooms"] if x["room_id"] == rid)
    assert row["display"]["timer_zoom_pct"] == 60


def test_only_this_rooms_proctor_may_set_it(monkeypatch):
    admin = staff(monkeypatch)
    a, b = make_room(admin, "Disp B")["room_id"], make_room(admin, "Disp C")["room_id"]
    p = proctor(monkeypatch, a)
    assert put(admin, a, timer_zoom_pct=90).status_code == 403  # admins don't resize (ADR 0019)
    assert put(screen(monkeypatch, a), a, timer_zoom_pct=90).status_code == 403  # no controls there
    assert put(p, b, timer_zoom_pct=90).status_code == 403  # another room
    assert put(mk(monkeypatch), a, timer_zoom_pct=90).status_code == 401
    assert put(p, "nope", timer_zoom_pct=90).status_code == 404
    body = {"command_id": str(uuid.uuid4()), "claimed_at_ms": now(), "timer_zoom_pct": 90}
    assert p.patch(f"/api/rooms/{a}/display", json=body).status_code == 400  # no client header
    assert put(p, a).status_code == 422  # nothing to change
    assert put(p, a, timer_zoom_pct=None, clar_size=None).status_code == 422
    for bad in ({"timer_zoom_pct": 85}, {"clar_size": 8}, {"clar_size": "huge"}, {"zoom": 1}):
        assert put(p, a, **bad).status_code == 422, bad
    assert p.get(f"/api/rooms/{a}/snapshot").json()["display"]["timer_zoom_at_ms"] is None


def test_deleted_room_refuses(monkeypatch):
    admin = staff(monkeypatch)
    rid = make_room(admin, "Disp D")["room_id"]
    p = proctor(monkeypatch, rid)
    assert admin.delete(f"/api/staff/rooms/{rid}", headers=H).status_code == 200
    assert put(p, rid, timer_zoom_pct=90).status_code == 404


def test_last_click_wins_not_last_arrival(monkeypatch):
    admin = staff(monkeypatch)
    rid = make_room(admin, "Disp E")["room_id"]
    p1, p2 = proctor(monkeypatch, rid), proctor(monkeypatch, rid)  # two proctors, one room
    t = now()
    s1 = put(p1, rid, at=t - 1000, timer_zoom_pct=90).json()
    late = put(p2, rid, at=t - 5000, timer_zoom_pct=40).json()  # clicked earlier, arrived later
    assert late["display"]["timer_zoom_pct"] == 90
    assert late["version"] == s1["version"]  # a losing click changes nothing at all
    newer = put(p2, rid, at=t - 500, timer_zoom_pct=50).json()
    assert (
        newer["display"]["timer_zoom_pct"] == 50 and newer["display"]["timer_zoom_at_ms"] == t - 500
    )


def test_fields_are_independent(monkeypatch):
    admin = staff(monkeypatch)
    rid = make_room(admin, "Disp F")["room_id"]
    p = proctor(monkeypatch, rid)
    t = now()
    put(p, rid, at=t - 100, clar_size=6)
    s = put(p, rid, at=t - 900, timer_zoom_pct=70).json()  # older click, but on the other field
    assert (s["display"]["timer_zoom_pct"], s["display"]["clar_size"]) == (70, 6)
    both = put(p, rid, at=t - 500, timer_zoom_pct=100, clar_size=1).json()  # wins timer only
    assert (both["display"]["timer_zoom_pct"], both["display"]["clar_size"]) == (100, 6)


def test_retry_is_a_no_op_even_after_newer_changes(monkeypatch):
    admin = staff(monkeypatch)
    rid = make_room(admin, "Disp G")["room_id"]
    p = proctor(monkeypatch, rid)
    t, cid = now(), str(uuid.uuid4())
    first = put(p, rid, at=t - 2000, cid=cid, timer_zoom_pct=60).json()
    again = put(p, rid, at=t - 2000, cid=cid, timer_zoom_pct=60).json()
    assert again["version"] == first["version"] and again["display"] == first["display"]
    put(p, rid, at=t - 1000, timer_zoom_pct=90)
    replay = put(p, rid, at=t - 2000, cid=cid, timer_zoom_pct=60).json()  # a slow duplicate
    assert replay["display"]["timer_zoom_pct"] == 90


def test_same_click_time_breaks_ties_by_command_id_in_any_order(monkeypatch):
    admin = staff(monkeypatch)
    lo, hi = "00000000-0000-4000-8000-000000000001", "ffffffff-ffff-4fff-bfff-ffffffffffff"
    t = now() - 1000
    for order in ((lo, hi), (hi, lo)):
        rid = make_room(admin, f"Disp H {order[0][:2]}")["room_id"]
        p = proctor(monkeypatch, rid)
        for cid in order:
            put(p, rid, at=t, cid=cid, timer_zoom_pct=40 if cid == lo else 100)
        assert p.get(f"/api/rooms/{rid}/snapshot").json()["display"]["timer_zoom_pct"] == 100


def test_a_click_from_the_future_counts_as_its_arrival(monkeypatch):
    admin = staff(monkeypatch)
    rid = make_room(admin, "Disp I")["room_id"]
    p = proctor(monkeypatch, rid)
    s = put(p, rid, at=now() + 3_600_000, timer_zoom_pct=40).json()  # device clock an hour fast
    assert s["display"]["timer_zoom_at_ms"] <= now()
    s2 = put(p, rid, timer_zoom_pct=70).json()  # so it can't lock out the next real click
    assert s2["display"]["timer_zoom_pct"] == 70
    assert put(p, rid, at=-5, clar_size=2).json()["display"]["clar_size_at_ms"] == 0


def test_kept_across_timer_reset_and_room_edits(monkeypatch):
    admin = staff(monkeypatch)
    snap = make_room(admin, "Disp J")
    rid = snap["room_id"]
    p = proctor(monkeypatch, rid)
    put(p, rid, timer_zoom_pct=50, clar_size=3)
    for kind in ("permit", "start", "pause"):
        assert (
            admin.post(
                "/api/commands",
                json={
                    "type": kind, "command_id": str(uuid.uuid4()), "device_id": str(uuid.uuid4()),
                    "room_id": rid, "session_id": snap["session_id"], "claimed_at_ms": 0,
                },
                headers=H,
            ).status_code
            == 200
        )  # fmt: skip
    reset = admin.post(
        f"/api/staff/rooms/{rid}/reset", json={"session_id": snap["session_id"]}, headers=H
    ).json()
    assert reset["session_id"] != snap["session_id"]
    edited = admin.patch(f"/api/staff/rooms/{rid}", json={"test_name": "Team"}, headers=H).json()
    assert (edited["display"]["timer_zoom_pct"], edited["display"]["clar_size"]) == (50, 3)


def test_a_change_is_streamed_to_the_rooms_devices(monkeypatch):
    monkeypatch.setenv("SEED_ROOMS", "One,Two")

    async def run() -> None:
        store = Store()
        gen = frames(store, "one", heartbeat_s=5)
        _, first = decode(await anext(gen))
        await store.set_display(store.rooms["two"], uuid.uuid4(), now(), {"clar_size": 4})
        await store.set_display(store.rooms["one"], uuid.uuid4(), now(), {"timer_zoom_pct": 100})
        ev, snap = decode(await asyncio.wait_for(anext(gen), 2))  # room one only
        assert ev == "snapshot" and snap["room_id"] == "one"
        assert snap["display"]["timer_zoom_pct"] == 100 and snap["display"]["clar_size"] == "auto"
        assert snap["version"] > first["version"]
        await gen.aclose()

    asyncio.run(run())


def test_db_column_round_trip_and_garbage_falls_back_to_defaults():
    d = {"timer_zoom_pct": Setting(60, 123, "a"), "clar_size": Setting("auto")}
    assert display_from_db(display_to_db(d)) == d
    assert display_to_db(d) == {"timer_zoom_pct": {"value": 60, "at_ms": 123, "by": "a"}}
    assert display_from_db('{"clar_size": {"value": 3, "at_ms": 9, "by": "b"}}')[
        "clar_size"
    ] == Setting(3, 9, "b")
    defaults = display_from_db("{}")
    for junk in (
        None, "", "not json", "[]", '{"timer_zoom_pct": 7}',
        '{"timer_zoom_pct": {"value": 85, "at_ms": 1}}', '{"clar_size": {"value": 8, "at_ms": 1}}',
        '{"clar_size": {"value": true, "at_ms": 1}}', '{"clar_size": {"value": 2}}',
    ):  # fmt: skip
        assert display_from_db(junk) == defaults, junk

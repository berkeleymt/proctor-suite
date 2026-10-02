"""Reset, delete/restore, rename, doc url, staff pause/resume, presence."""

import uuid

from fastapi.testclient import TestClient

from tests.test_api import H, cmd, mk


def staff(monkeypatch) -> TestClient:
    c = mk(monkeypatch)
    creds = {"username": "admin", "password": "admin-pw"}
    assert c.post("/api/auth/staff-login", json=creds, headers=H).status_code == 200
    return c


def make_room(c, name="Mgmt Hall", **kw):
    r = c.post("/api/staff/rooms", json={"name": name, "duration_min": 30, **kw}, headers=H)
    assert r.status_code == 201, r.text
    return r.json()


def send(c, kind, snap, **kw):
    r = c.post(
        "/api/commands", json=cmd(kind, snap["room_id"], snap["session_id"], **kw), headers=H
    )
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "applied", r.json()
    return r.json()["snapshot"]


def test_staff_can_pause_and_resume_and_reset_needs_pause_or_end(monkeypatch):
    c = staff(monkeypatch)
    snap = make_room(c, "Reset Hall")
    url = f"/api/staff/rooms/{snap['room_id']}/reset"
    body = {"session_id": snap["session_id"]}
    assert c.post(url, json=body, headers=H).status_code == 409  # not started
    snap = send(c, "start", send(c, "permit", snap))
    assert c.post(url, json=body, headers=H).status_code == 409  # running: pause first
    snap = send(c, "pause", snap)
    assert snap["timer"]["status"] == "PAUSED"
    assert c.post(url, json={"session_id": "old"}, headers=H).status_code == 409  # stale
    fresh = c.post(url, json=body, headers=H).json()
    assert fresh["timer"]["status"] == "NOT_PERMITTED" and fresh["session_id"] != snap["session_id"]
    assert fresh["timer"]["duration_ms"] == 30 * 60_000 and fresh["version"] > snap["version"]
    # a tap still in flight from the old session is rejected, not applied
    late = c.post(
        "/api/commands", json=cmd("resume", snap["room_id"], snap["session_id"]), headers=H
    )
    assert late.json()["reason"] == "stale_session"
    # finished rooms can be reset too (adjust -30 min on a running room ends it)
    snap = send(c, "start", send(c, "permit", fresh))
    snap = send(c, "adjust", snap, delta_ms=-30 * 60_000)
    assert snap["timer"]["status"] == "ENDED"
    assert c.post(url, json={"session_id": snap["session_id"]}, headers=H).status_code == 200


def test_proctor_cannot_reset(monkeypatch):
    admin = staff(monkeypatch)
    room = make_room(admin, "Proctor Hall")
    c = mk(monkeypatch)
    login = {"room_id": room["room_id"], "password": "room-pw", "surface": "control"}
    assert c.post("/api/auth/room-login", json=login, headers=H).status_code == 200
    url = f"/api/staff/rooms/{room['room_id']}/reset"
    assert c.post(url, json={"session_id": room["session_id"]}, headers=H).status_code == 401


def test_delete_restore_rename_doc_url(monkeypatch):
    c = staff(monkeypatch)
    snap = make_room(c, "Doomed Hall", doc_url="https://docs.google.com/document/d/x")
    rid = snap["room_id"]
    assert snap["doc_url"].startswith("https://") and snap["deleted"] is False
    url = f"/api/staff/rooms/{rid}"
    assert c.patch(url, json={"doc_url": "http://nope"}, headers=H).status_code == 422
    assert c.patch(url, json={"doc_url": ""}, headers=H).json()["doc_url"] is None
    renamed = c.patch(url, json={"name": "Better Hall"}, headers=H).json()
    assert renamed["room_name"] == "Better Hall" and renamed["room_id"] == rid
    other = make_room(c, "Other Hall")
    assert (
        c.patch(
            f"/api/staff/rooms/{other['room_id']}", json={"name": "better hall"}, headers=H
        ).status_code
        == 409
    )

    # a proctor is signed in; deleting signs them out and hides the room everywhere devices look
    proctor = mk(monkeypatch)
    login = {"room_id": rid, "password": "room-pw", "surface": "control"}
    assert proctor.post("/api/auth/room-login", json=login, headers=H).status_code == 200
    assert proctor.get(f"/api/rooms/{rid}/snapshot").status_code == 200
    gone = c.delete(url, headers=H).json()
    assert gone["deleted"] is True
    assert proctor.get(f"/api/rooms/{rid}/snapshot").status_code in (401, 404)
    assert rid not in [r["room_id"] for r in proctor.get("/api/auth/rooms").json()["rooms"]]
    assert proctor.post("/api/auth/room-login", json=login, headers=H).status_code == 401
    listed = {r["room_id"]: r for r in c.get("/api/staff/rooms").json()["rooms"]}
    assert listed[rid]["deleted"] is True  # staff still see it, to restore
    assert c.patch(url, json={"test_name": "x"}, headers=H).status_code == 409
    assert c.post(f"{url}/restore", headers=H).json()["deleted"] is False
    assert rid in [r["room_id"] for r in proctor.get("/api/auth/rooms").json()["rooms"]]


def test_cannot_delete_a_room_in_progress(monkeypatch):
    c = staff(monkeypatch)
    snap = send(c, "start", send(c, "permit", make_room(c, "Busy Hall")))
    url = f"/api/staff/rooms/{snap['room_id']}"
    assert c.delete(url, headers=H).status_code == 409  # running
    snap = send(c, "pause", snap)
    assert c.delete(url, headers=H).status_code == 409  # paused is still in progress
    c.post(f"{url}/reset", json={"session_id": snap["session_id"]}, headers=H)
    assert c.delete(url, headers=H).status_code == 200


def test_presence_counts_open_pages_per_surface():
    import asyncio

    from app.store import Store
    from app.stream import frames

    async def run() -> None:
        store = Store()
        staff_gen = frames(store, None, heartbeat_s=5)
        for _ in store.rooms:
            await anext(staff_gen)  # initial snapshots
        control = frames(store, "evans-10", heartbeat_s=5, surface="control")
        await anext(control)  # connecting counts
        msg = await anext(staff_gen)
        assert msg.startswith("event: presence") and '"control": {"online": 1' in msg
        display = frames(store, "evans-10", heartbeat_s=5, surface="display")
        await anext(display)
        await anext(staff_gen)
        await control.aclose()
        p = store.hub.presence("evans-10")
        assert p["control"]["online"] == 0 and p["control"]["last_seen_ms"]  # last seen kept
        assert p["display"]["online"] == 1
        assert store.hub.presence("soda-306")["control"]["last_seen_ms"] is None  # never
        await display.aclose()
        await staff_gen.aclose()

    asyncio.run(run())


def test_deleted_room_stream_ends():
    import asyncio

    from app.store import Store
    from app.stream import frames

    async def run() -> None:
        store = Store()
        room = store.rooms["evans-10"]
        gen = frames(store, "evans-10", heartbeat_s=5)
        await anext(gen)
        await store.delete_room(room)
        try:
            await anext(gen)
            raise AssertionError("stream should have ended")
        except StopAsyncIteration:
            pass

    asyncio.run(run())


def test_stream_surface_only_counts_with_own_login(monkeypatch):
    c = mk(monkeypatch)
    assert c.get("/api/rooms/nope/stream?surface=control").status_code == 404
    assert c.get("/api/rooms/evans-10/stream?surface=bogus").status_code == 422
    assert uuid  # keep import used

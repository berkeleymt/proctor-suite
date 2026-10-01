import uuid

from fastapi.testclient import TestClient

from app.main import app

H = {"X-Proctor-Client": "t"}


def mk(monkeypatch):
    monkeypatch.setenv("ROOM_PASSWORD", "room-pw")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pw")
    return TestClient(app, base_url="https://testserver")


def cmd(kind, room, session, **kw):
    return {
        "type": kind, "command_id": str(uuid.uuid4()), "device_id": str(uuid.uuid4()),
        "room_id": room, "session_id": session, "claimed_at_ms": 0, **kw,
    }  # fmt: skip


def test_rooms_and_time_are_public(monkeypatch):
    c = mk(monkeypatch)
    assert len(c.get("/api/auth/rooms").json()["rooms"]) >= 1
    assert c.get("/api/time").json()["server_time_ms"] > 0


def test_login_needs_header_and_password(monkeypatch):
    c = mk(monkeypatch)
    body = {"room_id": "evans-10", "password": "room-pw", "surface": "control"}
    assert c.post("/api/auth/room-login", json=body).status_code == 400
    bad = {**body, "password": "nope"}
    assert c.post("/api/auth/room-login", json=bad, headers=H).status_code == 401
    assert c.post("/api/auth/room-login", json=body, headers=H).status_code == 200
    assert c.get("/api/me?surface=control").json()["room_id"] == "evans-10"


def test_permit_then_start_loop_and_idempotency(monkeypatch):
    admin, room = mk(monkeypatch), mk(monkeypatch)
    admin.post(
        "/api/auth/staff-login", json={"username": "admin", "password": "admin-pw"}, headers=H
    )
    room.post("/api/auth/room-login", json={"room_id": "soda-306", "password": "room-pw", "surface": "control"}, headers=H)  # fmt: skip
    snap = room.get("/api/rooms/soda-306/snapshot").json()
    sid = snap["session_id"]
    assert snap["timer"]["status"] == "NOT_PERMITTED"
    # room cannot permit; admin can
    assert (
        room.post("/api/commands", json=cmd("permit", "soda-306", sid), headers=H).status_code
        == 403
    )
    p = cmd("permit", "soda-306", sid)
    r = admin.post("/api/commands", json=p, headers=H).json()
    assert r["outcome"] == "applied" and r["snapshot"]["timer"]["status"] == "PERMITTED"
    again = admin.post("/api/commands", json=p, headers=H).json()
    assert again["replayed"] is True
    changed = {**p, "type": "start"}
    assert admin.post("/api/commands", json=changed, headers=H).status_code == 409
    s = room.post("/api/commands", json=cmd("start", "soda-306", sid, claimed_at_ms=10**15), headers=H).json()  # fmt: skip
    assert s["outcome"] == "rejected"  # claimed_at in the future
    ok = admin.post("/api/commands", json=cmd("start", "soda-306", sid), headers=H).json()
    assert ok["snapshot"]["timer"]["status"] == "RUNNING"


def test_room_cannot_read_other_room(monkeypatch):
    c = mk(monkeypatch)
    c.post("/api/auth/room-login", json={"room_id": "evans-10", "password": "room-pw", "surface": "control"}, headers=H)  # fmt: skip
    assert c.get("/api/rooms/soda-306/snapshot").status_code == 401

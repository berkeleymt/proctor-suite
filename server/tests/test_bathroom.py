"""Bathroom log: out/back, idempotent retries, permissions, bounds, staff counts."""

import uuid

from tests.test_api import H, mk
from tests.test_room_management import make_room, staff


def proctor(monkeypatch, room_id):
    c = mk(monkeypatch)
    body = {"room_id": room_id, "password": "room-pw", "surface": "control"}
    assert c.post("/api/auth/room-login", json=body, headers=H).status_code == 200
    return c


def out(c, room_id, student="054a", vid=None):
    body = {"id": vid or str(uuid.uuid4()), "student_id": student}
    return c.post(f"/api/rooms/{room_id}/bathroom", json=body, headers=H)


def test_out_back_and_retry_is_idempotent(monkeypatch):
    admin = staff(monkeypatch)
    rid = make_room(admin, "Bath A")["room_id"]
    p = proctor(monkeypatch, rid)
    v0 = p.get(f"/api/rooms/{rid}/snapshot").json()["version"]
    vid = str(uuid.uuid4())
    s = out(p, rid, " 054a ", vid).json()
    assert [v["student_id"] for v in s["bathroom_out"]] == ["054A"] and s["students_out"] == 1
    assert s["version"] > v0
    again = out(p, rid, "054A", vid).json()  # same id: a retry, not a second entry
    assert again["students_out"] == 1 and again["version"] == s["version"]
    assert out(p, rid, "054A").status_code == 409  # already out
    assert out(p, rid, "999Z", vid).status_code == 409  # id reused for someone else
    back = p.post(f"/api/rooms/{rid}/bathroom/{vid}/return", headers=H).json()
    assert back["students_out"] == 0 and back["bathroom_out"] == []
    assert back["bathroom_back"][0]["back_ms"] >= back["bathroom_back"][0]["left_ms"]
    twice = p.post(f"/api/rooms/{rid}/bathroom/{vid}/return", headers=H).json()
    assert twice["version"] == back["version"]  # returning twice changes nothing
    assert out(p, rid, "054A").status_code == 200  # can go again
    assert p.post(f"/api/rooms/{rid}/bathroom/{uuid.uuid4()}/return", headers=H).status_code == 404


def test_who_may_log_and_validation(monkeypatch):
    admin = staff(monkeypatch)
    a, b = make_room(admin, "Bath B")["room_id"], make_room(admin, "Bath C")["room_id"]
    p = proctor(monkeypatch, a)
    assert out(p, b).status_code == 403  # another room's proctor
    anon = mk(monkeypatch)
    assert out(anon, a).status_code == 401
    assert out(admin, a, "117c").status_code == 200  # admins may too
    assert out(p, a, "   ").status_code == 422 and out(p, a, "x" * 21).status_code == 422
    assert out(p, "nope").status_code == 404
    assert anon.post(f"/api/rooms/{a}/bathroom", json={"id": "x"}).status_code in (400, 422)


def test_staff_list_has_counts_but_not_names(monkeypatch):
    admin = staff(monkeypatch)
    rid = make_room(admin, "Bath D")["room_id"]
    p = proctor(monkeypatch, rid)
    out(p, rid, "1"), out(p, rid, "2")
    row = next(r for r in admin.get("/api/staff/rooms").json()["rooms"] if r["room_id"] == rid)
    assert row["students_out"] == 2 and row["bathroom_out"] == [] and row["bathroom_back"] == []


def test_bounds(monkeypatch):
    admin = staff(monkeypatch)
    rid = make_room(admin, "Bath E")["room_id"]
    p = proctor(monkeypatch, rid)
    for i in range(50):
        assert out(p, rid, f"S{i}").status_code == 200
    assert out(p, rid, "S50").status_code == 409  # too many out at once
    s = p.get(f"/api/rooms/{rid}/snapshot").json()
    for v in s["bathroom_out"][:30]:
        p.post(f"/api/rooms/{rid}/bathroom/{v['id']}/return", headers=H)
    s = p.get(f"/api/rooms/{rid}/snapshot").json()
    assert len(s["bathroom_back"]) == 20 and s["students_out"] == 20  # only the latest 20 sent

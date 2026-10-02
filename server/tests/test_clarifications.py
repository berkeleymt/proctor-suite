"""Clarifications: post to all or some rooms, hide/unhide, visibility per room, versions."""

import uuid

from tests.test_api import H
from tests.test_room_management import make_room, staff


def snap(c, room_id):
    return c.get(f"/api/rooms/{room_id}/snapshot").json()


def room_login(c, room_id):
    body = {"room_id": room_id, "password": "room-pw", "surface": "display"}
    assert c.post("/api/auth/room-login", json=body, headers=H).status_code == 200


def test_post_hide_unhide_and_targeting(monkeypatch):
    c = staff(monkeypatch)
    a, b = make_room(c, "Clar A"), make_room(c, "Clar B")
    v0 = c.get(f"/api/rooms/{a['room_id']}/snapshot").json()["version"]
    everyone = c.post("/api/staff/clarifications", json={"body": "Calculators off"}, headers=H)
    only_b = c.post(
        "/api/staff/clarifications",
        json={"body": "- P7: positive integer", "room_ids": [b["room_id"]]},
        headers=H,
    )
    assert everyone.status_code == 201 and only_b.status_code == 201
    sa, sb = snap(c, a["room_id"]), snap(c, b["room_id"])
    assert [x["body"] for x in sa["clarifications"]] == ["Calculators off"]
    assert [x["body"] for x in sb["clarifications"]] == [
        "Calculators off",
        "- P7: positive integer",
    ]
    assert sa["version"] > v0  # a change reaches rooms through their version
    # polling client that already has this version gets 304; after a hide it does not
    url = f"/api/rooms/{a['room_id']}/snapshot?since_version={sa['version']}"
    assert c.get(url).status_code == 304
    cid = everyone.json()["id"]
    hid = c.patch(f"/api/staff/clarifications/{cid}", json={"hidden": True}, headers=H)
    assert hid.status_code == 200 and hid.json()["hidden"] is True
    assert c.get(url).status_code == 200
    assert snap(c, a["room_id"])["clarifications"] == []
    c.patch(f"/api/staff/clarifications/{cid}", json={"hidden": False}, headers=H)
    assert len(snap(c, a["room_id"])["clarifications"]) == 1
    listed = c.get("/api/staff/clarifications").json()["clarifications"]
    assert listed[0]["body"].startswith("- P7")  # newest first
    # staff room list stays small
    assert all(r["clarifications"] == [] for r in c.get("/api/staff/rooms").json()["rooms"])


def test_validation_and_permissions(monkeypatch):
    c = staff(monkeypatch)
    post = lambda **j: c.post("/api/staff/clarifications", json=j, headers=H)
    assert post(body="   ").status_code == 422
    assert post(body="x", room_ids=[]).status_code == 422  # empty list is not "all"
    assert post(body="x", room_ids=["nope"]).status_code == 422
    assert c.post("/api/staff/clarifications", json={"body": "x"}).status_code == 400  # header
    missing = str(uuid.uuid4())
    assert (
        c.patch(
            f"/api/staff/clarifications/{missing}", json={"hidden": True}, headers=H
        ).status_code
        == 404
    )
    c.cookies.clear()
    assert c.get("/api/staff/clarifications").status_code == 401
    room_login(c, "evans-10")  # a room device is not staff
    assert c.post("/api/staff/clarifications", json={"body": "x"}, headers=H).status_code == 401

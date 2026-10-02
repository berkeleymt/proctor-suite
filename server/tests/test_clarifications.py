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


def clar(c, body, rooms=None):
    j = {"body": body} if rooms is None else {"body": body, "room_ids": rooms}
    r = c.post("/api/staff/clarifications", json=j, headers=H)
    assert r.status_code == 201
    return r.json()["id"]


def mine(c, room_id, *ids):
    """This room's visible clarifications, limited to the ones the test made (the store is shared)."""
    return [x for x in snap(c, room_id)["clarifications"] if x["id"] in ids]


def test_edit_keeps_old_wording_visible(monkeypatch):
    c = staff(monkeypatch)
    a = make_room(c, "Edit A")["room_id"]
    cid = clar(c, "P7: integers")
    url = f"/api/staff/clarifications/{cid}"
    v = snap(c, a)["version"]
    r = c.patch(url, json={"body": "P7: positive integers"}, headers=H)
    assert r.status_code == 200 and r.json()["previous"] == ["P7: integers"]
    s = snap(c, a)
    assert s["version"] > v  # the room hears about it
    (x,) = mine(c, a, cid)
    assert x["body"] == "P7: positive integers" and x["previous"] == ["P7: integers"]
    assert x["edited_at_ms"] is not None
    # same text again is a no-op, blank is refused, and exactly one action per request
    assert c.patch(url, json={"body": "P7: positive integers"}, headers=H).status_code == 200
    assert len(mine(c, a, cid)[0]["previous"]) == 1
    assert c.patch(url, json={"body": "   "}, headers=H).status_code == 422
    assert c.patch(url, json={}, headers=H).status_code == 422
    assert c.patch(url, json={"body": "x", "hidden": True}, headers=H).status_code == 422
    assert c.patch(url, json={"body": "x", "room_id": a}, headers=H).status_code == 422
    for i in range(9):  # 10 edits is the cap
        assert c.patch(url, json={"body": f"v{i}"}, headers=H).status_code == 200
    over = c.patch(url, json={"body": "one too many"}, headers=H)
    assert over.status_code == 422 and over.json()["detail"]["error"] == "edit_limit"


def test_delete_everywhere_and_version_never_drops(monkeypatch):
    c = staff(monkeypatch)
    a = make_room(c, "Del A")["room_id"]
    cid = clar(c, "Oops")
    v = snap(c, a)["version"]
    assert c.delete(f"/api/staff/clarifications/{cid}", headers=H).status_code == 204
    s = snap(c, a)
    assert mine(c, a, cid) == [] and s["version"] > v
    assert all(x["id"] != cid for x in c.get("/api/staff/clarifications").json()["clarifications"])
    assert c.delete(f"/api/staff/clarifications/{cid}", headers=H).status_code == 404
    assert c.delete(f"/api/staff/clarifications/{cid}").status_code == 400  # header required


def test_per_room_hide_and_delete(monkeypatch):
    c = staff(monkeypatch)
    a, b, z = (make_room(c, n)["room_id"] for n in ("Pr A", "Pr B", "Pr Z"))
    everyone = clar(c, "For all")
    some = clar(c, "For A and B", [a, b])
    url = lambda cid: f"/api/staff/clarifications/{cid}"
    # hide in one room only
    r = c.patch(url(everyone), json={"hidden": True, "room_id": a}, headers=H)
    assert r.status_code == 200 and r.json()["hidden_room_ids"] == [a]
    ids = (everyone, some)
    assert mine(c, a, *ids) == [x for x in mine(c, a, some)] and len(mine(c, a, *ids)) == 1
    assert len(mine(c, b, *ids)) == 2
    c.patch(url(everyone), json={"hidden": False, "room_id": a}, headers=H)
    assert len(mine(c, a, *ids)) == 2
    # a room it was never posted to
    bad = c.patch(url(some), json={"hidden": True, "room_id": z}, headers=H)
    assert bad.status_code == 422 and bad.json()["detail"]["error"] == "not_in_room"
    ghost = c.patch(url(some), json={"hidden": True, "room_id": "nope"}, headers=H)
    assert ghost.json()["detail"]["error"] == "unknown_room"
    # delete from one room only: stays elsewhere, and is gone from this room for good
    assert c.delete(url(everyone) + f"?room_id={a}", headers=H).status_code == 204
    assert [x["body"] for x in mine(c, a, *ids)] == ["For A and B"]
    assert len(mine(c, b, *ids)) == 2 and len(mine(c, z, *ids)) == 1
    row = next(
        x
        for x in c.get("/api/staff/clarifications").json()["clarifications"]
        if x["id"] == everyone
    )
    assert row["removed_room_ids"] == [a] and row["room_ids"] is None
    again = c.delete(url(everyone) + f"?room_id={a}", headers=H)
    assert again.json()["detail"]["error"] == "not_in_room"
    # removing the last targeted room wipes the whole clarification
    c.delete(url(some) + f"?room_id={a}", headers=H)
    c.delete(url(some) + f"?room_id={b}", headers=H)
    listed = [x["id"] for x in c.get("/api/staff/clarifications").json()["clarifications"]]
    assert some not in listed and everyone in listed

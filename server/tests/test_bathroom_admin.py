"""Admin bathroom tab: list across rooms, proctors can't delete, soft delete / restore / empty,
names from the roster, and the roster itself (import, lookup, sync)."""

import uuid

import pytest

from app import api, roster
from app.store import Store, _slug
from tests.test_api import H, mk
from tests.test_bathroom import out, proctor
from tests.test_room_management import make_room, staff

STUDENTS = [
    roster.Student("054A", "Ada Lovelace", "Moor High", "Moor A", "Evans 10", "coach@moor.org"),
    roster.Student("117C", "Alan Turing", "Bletchley Prep", "B1", "Soda 306", "parent@bp.org"),
    roster.Student("140D", "Grace Hopper", "Moor High", "Moor B", "", ""),
]


def load(admin, monkeypatch, students=None):
    """Sync a roster the way production does, with ContestDojo's answer faked."""
    monkeypatch.setenv("CONTESTDOJO_API_TOKEN", "t")
    monkeypatch.setenv("CONTESTDOJO_EVENT_ID", "ev1")
    monkeypatch.setattr(api, "fetch_contestdojo", lambda *cfg: (students or STUDENTS, []))
    return admin.post("/api/staff/roster/sync", headers=H)


def act(admin, action, ids=None, all_=False):
    body = {"action": action, **({"ids": ids} if ids is not None else {"all": all_})}
    return admin.post("/api/staff/bathroom/action", json=body, headers=H)


@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    """Every test here gets its own Store (counts and the roster start empty, seed rooms exist)."""
    monkeypatch.setattr(api, "store", Store())


def setup(monkeypatch, *names):
    admin = staff(monkeypatch)
    ids = []
    for n in names:
        if _slug(n) not in api.store.rooms:
            make_room(admin, n)
        ids.append(_slug(n))
    return admin, ids


def test_admin_list_counts_filters_and_order(monkeypatch):
    admin, (a, b) = setup(monkeypatch, "Log A", "Log B")
    pa, pb = proctor(monkeypatch, a), proctor(monkeypatch, b)
    v1, v2 = str(uuid.uuid4()), str(uuid.uuid4())
    out(pa, a, "054A", v1), out(pa, a, "117C"), out(pb, b, "140D", v2)
    pa.post(f"/api/rooms/{a}/bathroom/{v1}/return", headers=H)
    r = admin.get("/api/staff/bathroom").json()  # default: out now, longest out first
    assert [e["student_id"] for e in r["entries"]] == ["117C", "140D"]
    assert (r["out_now"], r["returned"], r["deleted"], r["truncated"]) == (2, 1, 0, False)
    got = lambda **q: [
        e["student_id"] for e in admin.get("/api/staff/bathroom", params=q).json()["entries"]
    ]
    assert got(status="returned") == ["054A"]
    assert sorted(got(status="all")) == ["054A", "117C", "140D"]
    assert got(status="all", room_id=b) == ["140D"]
    assert got(status="all", q="log a") == ["117C", "054A"]  # both in Log A, newest first
    assert got(status="all", q="140") == ["140D"]
    cut = admin.get("/api/staff/bathroom", params={"status": "all", "limit": 2}).json()
    assert len(cut["entries"]) == 2 and cut["truncated"] is True and cut["returned"] == 1
    assert admin.get("/api/staff/bathroom", params={"limit": 5001}).status_code == 422


def test_only_admins_see_and_delete_proctors_cannot(monkeypatch):
    admin, (a,) = setup(monkeypatch, "Perm A")
    p = proctor(monkeypatch, a)
    vid = str(uuid.uuid4())
    out(p, a, "054A", vid)
    assert p.get("/api/staff/bathroom").status_code == 401  # a room login is not staff
    assert (
        p.post(
            "/api/staff/bathroom/action", json={"action": "delete", "all": True}, headers=H
        ).status_code
        == 401
    )
    assert mk(monkeypatch).get("/api/staff/bathroom").status_code == 401  # signed out
    assert p.get(f"/api/rooms/{a}/snapshot").json()["students_out"] == 1  # nothing was deleted
    assert act(admin, "delete", [vid]).json() == {"changed": 1, "skipped": 0}


def test_soft_delete_restore_empty_and_proctor_view(monkeypatch):
    admin, (a,) = setup(monkeypatch, "Del A")
    p = proctor(monkeypatch, a)
    v1, v2 = str(uuid.uuid4()), str(uuid.uuid4())
    out(p, a, "054A", v1), out(p, a, "117C", v2)
    p.post(f"/api/rooms/{a}/bathroom/{v2}/return", headers=H)
    v0 = p.get(f"/api/rooms/{a}/snapshot").json()["version"]
    assert act(admin, "delete", [v1, v2]).json()["changed"] == 2
    s = p.get(f"/api/rooms/{a}/snapshot").json()
    assert s["students_out"] == 0 and s["bathroom_out"] == [] and s["bathroom_back"] == []
    assert s["version"] > v0  # the proctor's page hears about it
    r = admin.get("/api/staff/bathroom", params={"status": "all", "deleted": True}).json()
    assert (
        [e["deleted"] for e in r["entries"]] == [True, True]
        and r["deleted"] == 2
        and r["out_now"] == 0
    )
    assert admin.get("/api/staff/bathroom", params={"status": "all"}).json()["entries"] == []
    assert act(admin, "delete", [v1]).json()["changed"] == 0  # already deleted: nothing to do
    assert out(p, a, "054A").status_code == 200  # a deleted record doesn't block going out again
    assert act(admin, "restore", [v1]).json() == {
        "changed": 0,
        "skipped": 1,
    }  # ...and isn't doubled
    assert act(admin, "restore", [v2]).json()["changed"] == 1
    assert [v["student_id"] for v in p.get(f"/api/rooms/{a}/snapshot").json()["bathroom_back"]] == [
        "117C"
    ]
    assert act(admin, "empty", [v2]).json()["changed"] == 0  # live records can't be emptied
    assert act(admin, "empty", all_=True).json()["changed"] == 1  # only v1 was deleted
    r = admin.get("/api/staff/bathroom", params={"status": "all", "deleted": True}).json()
    assert r["deleted"] == 0 and len(r["entries"]) == 2
    assert act(admin, "delete", all_=True).json()["changed"] == 2


def test_action_validation(monkeypatch):
    admin, _ = setup(monkeypatch, "Val A")
    post = lambda b: admin.post("/api/staff/bathroom/action", json=b, headers=H).status_code
    assert post({"action": "delete"}) == 422  # needs ids or all
    assert post({"action": "delete", "ids": [], "all": True}) == 422  # not both
    assert post({"action": "nuke", "all": True}) == 422
    assert post({"action": "delete", "ids": ["x"]}) == 422
    assert (
        admin.post("/api/staff/bathroom/action", json={"action": "delete", "all": True}).status_code
        == 400
    )  # CSRF header


def test_roster_import_lookup_and_names(monkeypatch):
    admin, (a, _b) = setup(monkeypatch, "Evans 10", "Soda 306")
    p = proctor(monkeypatch, a)
    lk = lambda c, i: c.get("/api/roster/lookup", params={"id": i}).json()
    assert lk(p, "054A") == {"roster_loaded": False, "student": None}  # nothing imported yet
    r = load(admin, monkeypatch)
    assert r.status_code == 200 and r.json() == {"count": 3, "notes": []}
    got = lk(p, " 054a ")
    assert got["roster_loaded"] and got["student"] == {
        "id": "054A", "name": "Ada Lovelace", "school": "Moor High", "team": "Moor A", "room": "Evans 10",
    }  # fmt: skip
    assert "contact" not in got["student"]  # proctors never get contact details
    assert lk(p, "999Z") == {"roster_loaded": True, "student": None}
    assert lk(admin, "117c")["student"]["room"] == "Soda 306"
    # the proctor's own list shows the name once they go out
    s = out(p, a, "054A").json()
    assert s["bathroom_out"][0]["student_name"] == "Ada Lovelace"
    # the admin list carries name and school; the staff room list stays free of names
    e = admin.get("/api/staff/bathroom").json()["entries"][0]
    assert (e["student_name"], e["school"], e["room_name"]) == (
        "Ada Lovelace",
        "Moor High",
        "Evans 10",
    )
    assert all(x["bathroom_out"] == [] for x in admin.get("/api/staff/rooms").json()["rooms"])
    assert (
        admin.get("/api/staff/bathroom", params={"q": "lovelace"}).json()["entries"][0][
            "student_id"
        ]
        == "054A"
    )


def test_roster_list_filters_status_and_permissions(monkeypatch):
    admin, (a,) = setup(monkeypatch, "Evans 10")
    p = proctor(monkeypatch, a)
    load(admin, monkeypatch)
    out(p, a, "054A")
    r = admin.get("/api/staff/roster").json()
    assert (r["total"], r["matching"], r["out_now"], r["source"], r["sync_available"]) == (
        3,
        3,
        1,
        "contestdojo",
        True,
    )
    assert r["rooms"] == ["Evans 10", "Soda 306"] and r["synced_at_ms"] > 0
    assert [s["name"] for s in r["students"]] == ["Ada Lovelace", "Alan Turing", "Grace Hopper"]
    assert r["students"][0]["out_since_ms"] and r["students"][1]["out_since_ms"] is None
    assert r["students"][0]["contact"] == "coach@moor.org"  # admins do see it
    only = admin.get("/api/staff/roster", params={"room": "evans 10"}).json()
    assert (
        [s["id"] for s in only["students"]] == ["054A"]
        and only["matching"] == 1
        and only["total"] == 3
    )
    assert [
        s["id"] for s in admin.get("/api/staff/roster", params={"room": ""}).json()["students"]
    ] == ["140D"]
    assert admin.get("/api/staff/roster", params={"q": "bletchley"}).json()["matching"] == 1
    assert p.get("/api/staff/roster").status_code == 401
    assert p.post("/api/staff/roster/sync", headers=H).status_code == 401
    assert p.post("/api/staff/roster/sync", headers=H).status_code == 401


def test_roster_clear(monkeypatch):
    admin, (a,) = setup(monkeypatch, "Evans 10")
    p = proctor(monkeypatch, a)
    load(admin, monkeypatch)
    assert p.post("/api/staff/roster/clear", headers=H).status_code == 401  # admins only
    assert admin.post("/api/staff/roster/clear").status_code == 400  # CSRF header needed
    r = admin.post("/api/staff/roster/clear", headers=H)
    assert r.status_code == 200 and r.json() == {"count": 3, "notes": []}
    assert admin.get("/api/staff/roster").json()["total"] == 0
    assert p.get("/api/roster/lookup", params={"id": "054A"}).json() == {
        "roster_loaded": False,
        "student": None,
    }


def test_sync_not_configured_then_configured(monkeypatch):
    admin, _ = setup(monkeypatch, "Evans 10")
    r = admin.post("/api/staff/roster/sync", headers=H)
    assert r.status_code == 503 and r.json()["detail"]["error"] == "not_configured"
    for k, v in {
        "CONTESTDOJO_API_TOKEN": "t",
        "CONTESTDOJO_EVENT_ID": "ev1",
    }.items():
        monkeypatch.setenv(k, v)
    assert admin.get("/api/staff/roster").json()["sync_available"] is True
    seen = []
    monkeypatch.setattr(
        api,
        "fetch_contestdojo",
        lambda *cfg: seen.append(cfg) or ([roster.Student("1A", "Sync Kid")], ["n"]),
    )
    r = admin.post("/api/staff/roster/sync", headers=H)
    assert r.json() == {"count": 1, "notes": ["n"]} and seen == [("t", "ev1")]
    assert admin.get("/api/staff/roster").json()["source"] == "contestdojo"

    def boom(*cfg):
        raise roster.RosterError("ContestDojo refused the token. Ask for a new API token.")

    monkeypatch.setattr(api, "fetch_contestdojo", boom)
    r = admin.post("/api/staff/roster/sync", headers=H)
    assert r.status_code == 502 and "refused" in r.json()["detail"]["message"]
    assert admin.get("/api/staff/roster").json()["total"] == 1  # a failed sync keeps the old roster


class FakeResp:
    def __init__(self, status, data):
        self.status_code, self._d, self.ok = status, data, status < 400

    def json(self):
        return self._d


def test_fetch_contestdojo_maps_students_teams_orgs(monkeypatch):
    calls = []
    data = {
        "/events/ev1/students/": [
            {"number": "054a", "fname": "Ada", "lname": "L", "email": "a@x.org", "org": "o1", "team": "t1",
             "roomAssignments": {"test": "Evans 10"}},
            {"number": "", "fname": "No", "lname": "Number"},
        ],
        "/events/ev1/teams/": [{"id": "t1", "name": "Moor A"}],
        "/events/ev1/orgs/": [{"id": "o1", "name": "Moor High"}],
    }  # fmt: skip

    def fake_get(url, headers, timeout):
        path = url.removeprefix(roster.CONTESTDOJO_URL)
        calls.append((path, headers["Authorization"]))
        return FakeResp(200, data[path])

    monkeypatch.setattr(roster.requests, "get", fake_get)
    got, _ = roster.fetch_contestdojo("tok", "ev1")
    assert got == [
        roster.Student("054A", "Ada L", "Moor High", "Moor A", "", "a@x.org"),
        roster.Student("ROW2", "No Number", "", "", "", ""),  # no number: still imported
    ]
    assert calls[0] == ("/events/ev1/students/", "Bearer tok")


def test_fetch_contestdojo_imports_everything_even_without_numbers_or_orgs(monkeypatch):
    def fake_get(url, headers, timeout):
        if url.endswith("/students/"):
            return FakeResp(200, [
                {"id": "u1", "fname": "A", "lname": "B", "customFields": {"school": "Fallback HS"}},
                {"id": "u2", "fname": "C", "lname": "D"},
            ])  # fmt: skip
        return FakeResp(404, {})  # orgs and teams unavailable

    monkeypatch.setattr(roster.requests, "get", fake_get)
    got, notes = roster.fetch_contestdojo("tok", "ev1")
    assert [(s.id, s.school) for s in got] == [("U1", "Fallback HS"), ("U2", "")]
    assert notes == ["ContestDojo sent 2 students, 0 teams, 0 orgs; 0 have a number."]


@pytest.mark.parametrize(("status", "words"), [(401, "refused"), (404, "event"), (500, "500")])
def test_fetch_contestdojo_errors_are_plain(monkeypatch, status, words):
    monkeypatch.setattr(roster.requests, "get", lambda *a, **k: FakeResp(status, {}))
    with pytest.raises(roster.RosterError, match=words):
        roster.fetch_contestdojo("tok", "ev1")


def test_roster_set_room_and_sync_keeps_it(monkeypatch):
    admin, _ = setup(monkeypatch, "Evans 10")
    load(admin, monkeypatch)
    r = admin.post(
        "/api/staff/roster/room", json={"ids": ["140d", "NOPE"], "room": " Soda 306 "}, headers=H
    )
    assert r.json() == {"count": 1, "notes": []}
    rows = {s["id"]: s["room"] for s in admin.get("/api/staff/roster").json()["students"]}
    assert rows["140D"] == "Soda 306" and rows["054A"] == "Evans 10"
    load(admin, monkeypatch, [roster.Student("140D", "Grace Hopper"), roster.Student("9Z", "New")])
    rows = {s["id"]: s["room"] for s in admin.get("/api/staff/roster").json()["students"]}
    assert rows == {"140D": "Soda 306", "9Z": ""}  # kept by name; the new student has none
    assert (
        admin.post("/api/staff/roster/room", json={"ids": ["140D"], "room": ""}, headers=H).json()[
            "count"
        ]
        == 1
    )
    assert (
        admin.post("/api/staff/roster/room", json={"ids": ["x"], "room": "r"}).status_code == 400
    )  # CSRF

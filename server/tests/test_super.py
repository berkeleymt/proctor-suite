"""Branding, Google sign-in (token check faked), settings, passwords, super-admin list."""

import pytest

from app import google_auth
from app.api import store
from tests.test_api import H, mk


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id.apps.googleusercontent.com")
    monkeypatch.setenv("SUPER_ADMIN_EMAILS", "Boss@berkeley.mt")
    monkeypatch.setenv("APP_NAME", "Lemon")
    monkeypatch.setenv("APP_ICON", "logo.png")
    yield
    store.settings.clear()
    store.supers.clear()
    store.sessions.clear()


def fake_google(monkeypatch, email, verified=True, ok=True):
    def verify(credential, client_id):
        assert client_id == "client-id.apps.googleusercontent.com"
        if not ok:
            raise ValueError("bad token")
        return {"email": email, "email_verified": verified}

    monkeypatch.setattr(google_auth, "verify", verify)


def sign_in(monkeypatch, email="boss@berkeley.mt"):
    c = mk(monkeypatch)
    fake_google(monkeypatch, email)
    r = c.post("/api/auth/super-login", json={"credential": "x" * 40}, headers=H)
    assert r.status_code == 200, r.text
    return c


def test_brand_comes_from_env_then_settings(monkeypatch):
    c = mk(monkeypatch)
    assert c.get("/api/brand").json() == {"name": "Lemon", "icon": "/logo.png"}  # relative -> root
    monkeypatch.setenv("APP_ICON", "https://cdn.example.com/l.svg")
    assert c.get("/api/brand").json()["icon"] == "https://cdn.example.com/l.svg"
    monkeypatch.delenv("APP_NAME")
    assert c.get("/api/brand").json()["name"] == ""  # nothing is hard-coded
    assert c.get("/api/auth/super-config").json() == {
        "google_client_id": "client-id.apps.googleusercontent.com"
    }


def test_login_rules(monkeypatch):
    c = mk(monkeypatch)
    body = {"credential": "x" * 40}
    assert c.get("/api/super/settings").status_code == 401
    fake_google(monkeypatch, "boss@berkeley.mt", ok=False)
    assert c.post("/api/auth/super-login", json=body, headers=H).status_code == 401
    fake_google(monkeypatch, "stranger@gmail.com")
    r = c.post("/api/auth/super-login", json=body, headers=H)
    assert r.status_code == 403 and r.json()["detail"]["error"] == "not_allowed"
    fake_google(monkeypatch, "boss@berkeley.mt", verified=False)
    assert c.post("/api/auth/super-login", json=body, headers=H).status_code == 403
    fake_google(monkeypatch, "BOSS@berkeley.mt")  # Google's casing doesn't matter
    assert c.post("/api/auth/super-login", json=body, headers=H).json() == {
        "email": "boss@berkeley.mt"
    }
    assert c.get("/api/super/me").json() == {"email": "boss@berkeley.mt"}
    assert c.post("/api/auth/super-login", json=body).status_code == 400  # header required
    monkeypatch.delenv("GOOGLE_CLIENT_ID")
    assert c.post("/api/auth/super-login", json=body, headers=H).status_code == 503
    assert c.get("/api/auth/super-config").json() == {"google_client_id": None}
    c.post("/api/auth/super-logout", headers=H)
    assert c.get("/api/super/me").status_code == 401


def test_room_and_admin_sessions_are_not_super(monkeypatch):
    c = mk(monkeypatch)
    creds = {"username": "admin", "password": "admin-pw"}
    assert c.post("/api/auth/staff-login", json=creds, headers=H).status_code == 200
    assert c.get("/api/super/settings").status_code == 401  # the admin password isn't enough


def test_change_passwords_and_log_out_old(monkeypatch):
    c = sign_in(monkeypatch)
    rooms = mk(monkeypatch)
    room_id = rooms.get("/api/auth/rooms").json()["rooms"][0]["room_id"]
    login = {"room_id": room_id, "password": "room-pw", "surface": "control"}
    assert rooms.post("/api/auth/room-login", json=login, headers=H).status_code == 200
    assert rooms.get("/api/me?surface=control").status_code == 200
    got = c.get("/api/super/settings")
    assert got.headers["cache-control"] == "no-store" and got.json()["room_password"] == "room-pw"
    r = c.patch(
        "/api/super/settings", json={"room_password": "new-room-pw", "log_out_old": True}, headers=H
    )
    assert r.status_code == 200 and r.json()["room_password"] == "new-room-pw"
    assert rooms.get("/api/me?surface=control").status_code == 401  # signed out
    assert c.get("/api/super/me").status_code == 200  # the super-admin stays in
    assert rooms.post("/api/auth/room-login", json=login, headers=H).status_code == 401
    login["password"] = "new-room-pw"
    assert rooms.post("/api/auth/room-login", json=login, headers=H).status_code == 200
    # without the box, existing sessions survive; admin password too
    c.patch("/api/super/settings", json={"admin_password": "new-admin-pw"}, headers=H)
    assert rooms.get("/api/me?surface=control").status_code == 200
    staff = {"username": "admin", "password": "new-admin-pw"}
    assert mk(monkeypatch).post("/api/auth/staff-login", json=staff, headers=H).status_code == 200


def test_settings_validation_and_branding_change(monkeypatch):
    c = sign_in(monkeypatch)
    patch = lambda **j: c.patch("/api/super/settings", json=j, headers=H)
    assert patch(room_password="short").status_code == 422
    assert patch(app_name="  ").status_code == 422
    assert patch(app_icon="javascript://x").status_code == 422
    assert patch(app_icon="has space.png").status_code == 422
    assert patch(unknown=1).status_code == 422
    r = patch(app_name="Lemma", app_icon="/lemma.svg")
    assert r.status_code == 200
    assert c.get("/api/brand").json() == {"name": "Lemma", "icon": "/lemma.svg"}
    assert patch(app_icon="").status_code == 200
    assert c.get("/api/brand").json()["icon"] == ""  # empty on purpose = no icon


def test_super_admin_list(monkeypatch):
    c = sign_in(monkeypatch)
    assert [(a["email"], a["source"]) for a in c.get("/api/super/admins").json()["admins"]] == [
        ("boss@berkeley.mt", "env")
    ]
    add = lambda e: c.post("/api/super/admins", json={"email": e}, headers=H)
    assert add("not-an-email").status_code == 422
    r = add(" Helper@Berkeley.MT ")
    assert r.status_code == 201
    assert [a["email"] for a in r.json()["admins"]] == ["boss@berkeley.mt", "helper@berkeley.mt"]
    assert add("helper@berkeley.mt").status_code == 409
    assert add("boss@berkeley.mt").status_code == 409
    # the new one can sign in, and can remove the others but not themselves or the .env one
    helper = mk(monkeypatch)
    fake_google(monkeypatch, "helper@berkeley.mt")
    assert (
        helper.post("/api/auth/super-login", json={"credential": "x" * 40}, headers=H).status_code
        == 200
    )
    rm = lambda cl, e: cl.delete(f"/api/super/admins/{e}", headers=H)
    assert rm(helper, "helper@berkeley.mt").json()["detail"]["error"] == "cannot_remove_self"
    assert rm(helper, "boss@berkeley.mt").json()["detail"]["error"] == "set_in_env"
    assert rm(helper, "ghost@berkeley.mt").status_code == 404
    assert rm(c, "helper@berkeley.mt").status_code == 200
    assert helper.get("/api/super/me").status_code == 401  # removed = kicked out at once

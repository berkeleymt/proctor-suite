from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz_ok():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.text == "ok"


def test_readyz_without_database_url_is_503(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    r = client.get("/readyz")
    assert r.status_code == 503


def test_readyz_unreachable_database_is_503(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@127.0.0.1:1/z")
    r = client.get("/readyz")
    assert r.status_code == 503

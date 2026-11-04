import pytest

from app import create_app
from app.config import Config, TestConfig


def test_healthz_without_db():
    class NoDB(TestConfig):
        DATABASE_URL = ""

    res = create_app(NoDB).test_client().get("/healthz")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok", "db": "skipped"}


def test_healthz_db_unreachable():
    class BadDB(TestConfig):
        DATABASE_URL = "postgresql://nobody@127.0.0.1:1/none?connect_timeout=1"

    res = create_app(BadDB).test_client().get("/healthz")
    assert res.status_code == 503
    assert res.get_json()["db"] == "error"


def test_healthz_ok(client):
    res = client.get("/healthz", headers={"Host": "anything.internal"})  # Host チェック対象外
    assert res.status_code == 200
    assert res.get_json()["db"] == "ok"


def test_production_refuses_missing_secrets():
    class Prod(Config):
        SECRET_KEY = ""
        DATABASE_URL = ""
        APP_ENCRYPTION_KEY = ""

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(Prod)


def test_security_headers(client):
    res = client.get("/login")
    assert "default-src 'self'" in res.headers["Content-Security-Policy"]
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Cache-Control"] == "no-store"
    assert res.headers["X-Content-Type-Options"] == "nosniff"

"""テストは TEST_DATABASE_URL（ローカル Postgres / CI の service / Neon の test ブランチ）の
使い捨てスキーマ pytest_xxxx の中だけで動く。public スキーマや本番データには触らない。
"""

import os
import re
import secrets

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from app import create_app, db
from app.auth import upsert_user
from app.config import TestConfig
from app.crypto import generate_key

TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
requires_test_db = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL が未設定")
PASSWORD = "correct-horse-battery"  # betterleaks:allow（テスト専用）


@pytest.fixture(scope="session")
def schema_url():
    if not TEST_URL:
        pytest.skip("TEST_DATABASE_URL が未設定")
    schema = f"pytest_{secrets.token_hex(4)}"
    with psycopg.connect(TEST_URL, autocommit=True) as conn:
        conn.execute(f"CREATE SCHEMA {schema}")
    url = make_conninfo(TEST_URL, options=f"-csearch_path={schema}")
    with db.connect(url) as conn:
        db.apply_schema(conn)
    yield url
    with psycopg.connect(TEST_URL, autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA {schema} CASCADE")


@pytest.fixture
def app(schema_url):
    with psycopg.connect(schema_url, autocommit=True) as conn:
        conn.execute("TRUNCATE moves, items, login_failures, users RESTART IDENTITY CASCADE")

    class Cfg(TestConfig):
        DATABASE_URL = schema_url
        APP_ENCRYPTION_KEY = generate_key()

    app = create_app(Cfg)
    with app.app_context():
        upsert_user("owner", PASSWORD, "owner")
        upsert_user("staff", PASSWORD, "staff")
        db.close_conn()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_from(client, path="/login") -> str:
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def login(client, login_id, password=PASSWORD):
    token = csrf_from(client)
    return client.post("/login", data={"login_id": login_id, "password": password, "csrf_token": token})


@pytest.fixture
def owner(client):
    login(client, "owner")
    return client


@pytest.fixture
def staff(client):
    login(client, "staff")
    return client


def post(client, path, data=None):
    """CSRF トークン付きで POST する。"""
    token = csrf_from(client, "/")
    return client.post(path, data={**(data or {}), "csrf_token": token})


def add_item(client, **kw):
    data = {"name": "ブラジル サントス", "category": "コーヒー豆", "unit": "g",
            "threshold": "500", "lead_days": "3", **kw}
    res = post(client, "/items/new", data)
    assert res.status_code == 302, res.get_data(as_text=True)
    return int(res.headers["Location"].rsplit("/", 1)[1])

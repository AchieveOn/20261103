import pytest

from app.auth import safe_next, upsert_user

from .conftest import PASSWORD, add_item, csrf_from, login, post


def test_pages_require_login(client):
    res = client.get("/")
    assert res.status_code == 302
    assert res.headers["Location"].startswith("/login")


def test_login_and_logout(client):
    assert login(client, "staff").status_code == 302
    assert client.get("/").status_code == 200
    post(client, "/logout")
    assert client.get("/").status_code == 302


def test_wrong_password_same_message_as_unknown_id(client):
    a = login(client, "staff", "wrong-password-xx")
    b = login(client, "nobody", "wrong-password-xx")
    assert a.status_code == b.status_code == 401
    assert "IDまたはパスワードが違います" in a.get_data(as_text=True)
    assert "IDまたはパスワードが違います" in b.get_data(as_text=True)


def test_lockout_after_5_failures(client):
    for _ in range(5):
        login(client, "staff", "wrong-password-xx")
    res = login(client, "staff")   # 正しいパスワードでもロック中は入れない
    assert res.status_code == 429


def test_old_cookie_invalid_after_logout(app):
    c1 = app.test_client()
    login(c1, "staff")
    with c1.session_transaction() as s:
        stolen = dict(s)
    post(c1, "/logout")
    c2 = app.test_client()
    with c2.session_transaction() as s:
        s.update(stolen)
    assert c2.get("/").status_code == 302


def test_csrf_required(staff):
    res = staff.post("/logout")
    assert res.status_code == 403


def test_login_form_requires_csrf(client):
    res = client.post("/login", data={"login_id": "staff", "password": PASSWORD})
    assert res.status_code == 403


def test_bad_host_rejected(client):
    assert client.get("/login", headers={"Host": "evil.example"}).status_code == 400


def test_disabled_user_cannot_login(app, client):
    with app.app_context():
        from app.db import query
        query("UPDATE users SET active = FALSE WHERE login_id = 'staff'")
    assert login(client, "staff").status_code == 401


def test_staff_forbidden(app):
    owner = app.test_client()
    login(owner, "owner")
    item_id = add_item(owner)

    staff = app.test_client()
    login(staff, "staff")
    assert staff.get("/items/new").status_code == 403
    assert staff.get(f"/items/{item_id}/edit").status_code == 403
    assert post(staff, f"/items/{item_id}/archive").status_code == 403


@pytest.mark.parametrize("url,expected", [
    ("/items/1", "/items/1"),
    ("//evil.example", "/"),
    ("https://evil.example", "/"),
    ("/\\evil.example", "/"),
    (None, "/"),
])
def test_safe_next(url, expected):
    assert safe_next(url) == expected


def test_password_policy(app):
    with app.app_context(), pytest.raises(ValueError):
        upsert_user("x", "short", "staff")


def test_login_page_has_token(client):
    assert len(csrf_from(client)) > 20

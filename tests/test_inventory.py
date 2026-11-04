from app.db import query

from .conftest import add_item, login, post


def stock_of(app, item_id):
    with app.app_context():
        from app.inventory import load_item
        return load_item(item_id)["stock"]


def record(client, item_id, kind, qty, note=""):
    return post(client, f"/items/{item_id}/moves", {"kind": kind, "qty": str(qty), "note": note})


def test_stock_is_sum_of_moves(app, owner):
    item = add_item(owner)
    record(owner, item, "in", 1000)
    record(owner, item, "out", 300)
    assert stock_of(app, item) == 700
    record(owner, item, "count", 650)   # 棚卸しで実在庫に合わせる
    assert stock_of(app, item) == 650


def test_cannot_use_more_than_stock(app, owner):
    item = add_item(owner)
    record(owner, item, "in", 100)
    res = record(owner, item, "out", 101)
    assert res.status_code == 302
    assert stock_of(app, item) == 100


def test_invalid_qty_rejected(app, owner):
    item = add_item(owner)
    record(owner, item, "in", 0)
    record(owner, item, "in", "abc")
    record(owner, item, "hack", 10)
    assert stock_of(app, item) == 0


def test_staff_can_record_and_is_logged(app):
    owner = app.test_client()
    login(owner, "owner")
    item = add_item(owner)
    staff = app.test_client()
    login(staff, "staff")
    record(staff, item, "in", 50)
    html = staff.get(f"/items/{item}").get_data(as_text=True)
    assert "staff" in html
    assert stock_of(app, item) == 50


def test_void_keeps_history(app, owner):
    item = add_item(owner)
    record(owner, item, "in", 100)
    record(owner, item, "out", 30)
    with app.app_context():
        out_id = query("SELECT id FROM moves WHERE kind = 'out'", one=True)["id"]
    post(owner, f"/moves/{out_id}/void")
    assert stock_of(app, item) == 100
    with app.app_context():
        assert query("SELECT count(*) AS n FROM moves", one=True)["n"] == 2   # 消さずに残す


def test_void_blocked_if_stock_goes_negative(app, owner):
    item = add_item(owner)
    record(owner, item, "in", 100)
    record(owner, item, "out", 80)
    with app.app_context():
        in_id = query("SELECT id FROM moves WHERE kind = 'in'", one=True)["id"]
    post(owner, f"/moves/{in_id}/void")
    assert stock_of(app, item) == 20


def test_staff_cannot_void(app):
    owner = app.test_client()
    login(owner, "owner")
    item = add_item(owner)
    record(owner, item, "in", 100)
    staff = app.test_client()
    login(staff, "staff")
    with app.app_context():
        mid = query("SELECT id FROM moves", one=True)["id"]
    assert post(staff, f"/moves/{mid}/void").status_code == 403


def test_secret_fields_encrypted_at_rest(app, owner):
    item = add_item(owner, supplier="丸山珈琲商会", unit_cost="1850", note="月末締め")
    with app.app_context():
        row = query("SELECT supplier_enc, unit_cost_enc, note_enc FROM items WHERE id = %s", (item,), one=True)
    raw = " ".join(row.values())
    assert "丸山珈琲商会" not in raw and "1850" not in raw and "月末締め" not in raw
    assert all(v.startswith("gAAAA") for v in row.values())   # Fernet トークン


def test_owner_sees_secret_staff_does_not(app):
    owner = app.test_client()
    login(owner, "owner")
    item = add_item(owner, supplier="丸山珈琲商会", unit_cost="1850")
    assert "丸山珈琲商会" in owner.get(f"/items/{item}").get_data(as_text=True)

    staff = app.test_client()
    login(staff, "staff")
    html = staff.get(f"/items/{item}").get_data(as_text=True)
    assert "丸山珈琲商会" not in html and "1850" not in html


def test_edit_and_archive(app, owner):
    item = add_item(owner)
    res = post(owner, f"/items/{item}/edit", {"name": "ブラジル No.2", "category": "コーヒー豆",
                                              "unit": "g", "threshold": "800", "lead_days": "5"})
    assert res.status_code == 302
    assert "ブラジル No.2" in owner.get("/").get_data(as_text=True)
    post(owner, f"/items/{item}/archive")
    assert "ブラジル No.2" not in owner.get("/").get_data(as_text=True)


def test_item_validation(owner):
    res = post(owner, "/items/new", {"name": "", "category": "コーヒー豆", "unit": "g"})
    assert res.status_code == 400
    res = post(owner, "/items/new", {"name": "x", "category": "不正", "unit": "g"})
    assert res.status_code == 400


def test_levels(app, owner):
    empty = add_item(owner, name="A")
    reorder = add_item(owner, name="B", threshold="500")
    ok = add_item(owner, name="C", threshold="10")
    record(owner, reorder, "in", 400)
    record(owner, ok, "in", 1000)
    with app.app_context():
        from app.inventory import load_items
        levels = {i["name"]: i["level"] for i in load_items()}
    assert levels == {"A": "empty", "B": "reorder", "C": "ok"}
    html = owner.get("/").get_data(as_text=True)
    assert html.index(">A<") < html.index(">B<") < html.index(">C<")   # 危ない順に並ぶ
    assert empty

"""発注リスト（/orders）: 発注が必要な品目を仕入先ごとにまとめる。仕入先は秘匿情報なので店主だけ。"""

import re

from .conftest import add_item, login, post


def record(client, item_id, kind, qty):
    return post(client, f"/items/{item_id}/moves", {"kind": kind, "qty": str(qty)})


def orders_html(client) -> str:
    res = client.get("/orders")
    assert res.status_code == 200
    return res.get_data(as_text=True)


def row_of(html: str, name: str) -> str:
    return next(tr for tr in re.findall(r"<tr.*?</tr>", html, re.S) if name in tr)


def test_orders_is_owner_only(app):
    assert app.test_client().get("/orders").status_code == 302  # 未ログインはログイン画面へ
    staff = app.test_client()
    login(staff, "staff")
    assert staff.get("/orders").status_code == 403


def test_nav_link_only_for_owner(app, owner):
    assert 'href="/orders"' in owner.get("/").get_data(as_text=True)
    staff = app.test_client()
    login(staff, "staff")
    assert 'href="/orders"' not in staff.get("/").get_data(as_text=True)


def test_lists_only_items_that_need_ordering(owner):
    add_item(owner, name="空のA")  # 在庫 0 → 在庫切れ
    low = add_item(owner, name="少ないB", threshold="500")
    enough = add_item(owner, name="十分C", threshold="10")
    record(owner, low, "in", 400)  # 発注点 500 以下 → 要発注
    record(owner, enough, "in", 1000)
    html = orders_html(owner)
    assert "空のA" in html and "少ないB" in html
    assert "十分C" not in html


def test_grouped_by_supplier_with_unregistered_last(owner):
    add_item(owner, name="豆いち", supplier="北浜珈琲商会")
    add_item(owner, name="牛乳", supplier="みどり乳業", category="乳製品", unit="本")
    add_item(owner, name="紙ナプキン", category="消耗品", unit="袋")  # 仕入先なし
    add_item(owner, name="豆に", supplier="北浜珈琲商会")
    html = orders_html(owner)
    pos = html.index
    assert pos("みどり乳業") < pos("北浜珈琲商会") < pos("仕入先未登録")  # 仕入先の名前順・未登録は最後
    assert pos("みどり乳業") < pos("牛乳") < pos("北浜珈琲商会")
    assert pos("北浜珈琲商会") < pos("豆いち") < pos("仕入先未登録")
    assert pos("北浜珈琲商会") < pos("豆に") < pos("仕入先未登録")
    assert pos("仕入先未登録") < pos("紙ナプキン")
    assert html.count("北浜珈琲商会") == 1  # 同じ仕入先は1つにまとまる


def test_row_shows_stock_and_suggested_quantity(owner):
    low = add_item(owner, name="少ないB", threshold="500")
    record(owner, low, "in", 400)
    row = row_of(orders_html(owner), "少ないB")
    assert "要発注" in row and "400" in row and "100" in row  # 目安 = 500 + 0 − 400


def test_archived_items_are_not_listed(owner):
    item = add_item(owner, name="終売品")
    post(owner, f"/items/{item}/archive")
    assert "終売品" not in orders_html(owner)


def test_message_when_nothing_to_order(owner):
    item = add_item(owner, name="十分C", threshold="0")
    record(owner, item, "in", 10)
    html = orders_html(owner)
    assert "発注が必要な品目はありません" in html and "十分C" not in html


def test_suggested_quantity():
    from app.inventory import suggest_qty

    # 発注点 + 届くまでの使用見込み（1日の使用 × 届くまでの日数、切り上げ）− 在庫。0 未満は 0
    assert suggest_qty({"stock": 400, "threshold": 500, "per_day": 0, "lead_days": 3}) == 100
    assert suggest_qty({"stock": 400, "threshold": 500, "per_day": 50, "lead_days": 3}) == 250
    assert suggest_qty({"stock": 0, "threshold": 0, "per_day": 2.5, "lead_days": 3}) == 8
    assert suggest_qty({"stock": 900, "threshold": 500, "per_day": 10, "lead_days": 3}) == 0

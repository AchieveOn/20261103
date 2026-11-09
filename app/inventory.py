"""在庫の画面と記録。在庫 = moves.delta の合計（取消済みを除く）。在庫数を直接書き換えない。"""

import math
from datetime import timedelta

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from . import crypto
from .auth import owner_required, utcnow
from .db import get_conn, query

bp = Blueprint("inventory", __name__)

CATEGORIES = ["コーヒー豆", "茶葉", "乳製品", "フード", "シロップ・調味料", "消耗品"]
UNITS = ["g", "ml", "個", "本", "枚", "袋", "パック"]
LEVEL_ORDER = {"empty": 0, "reorder": 1, "soon": 2, "ok": 3}
LEVEL_LABEL = {"empty": "在庫切れ", "reorder": "要発注", "soon": "まもなく", "ok": "十分"}
KIND_LABEL = {"in": "入荷", "out": "使用", "count": "棚卸し"}
NO_SUPPLIER = "仕入先未登録"

STATUS_SQL = """
SELECT i.*,
       COALESCE(SUM(m.delta) FILTER (WHERE m.voided_at IS NULL), 0)::int AS stock,
       COALESCE(-SUM(m.delta) FILTER (WHERE m.voided_at IS NULL AND m.kind = 'out'
                                       AND m.created_at >= %(since)s), 0)::int AS used_recent
FROM items i LEFT JOIN moves m ON m.item_id = i.id
WHERE NOT i.archived {where}
GROUP BY i.id
"""


def _key() -> str:
    return current_app.config["APP_ENCRYPTION_KEY"]


def with_status(row: dict) -> dict:
    window = current_app.config["AVG_WINDOW_DAYS"]
    age_days = (utcnow() - row["created_at"]).total_seconds() / 86400
    span = max(1.0, min(window, age_days))  # 登録して日が浅い品目は経過日数で割る
    per_day = row["used_recent"] / span
    days_left = row["stock"] / per_day if per_day > 0 else None

    if row["stock"] <= 0:
        level = "empty"
    elif row["stock"] <= row["threshold"]:
        level = "reorder"
    elif days_left is not None and days_left <= row["lead_days"]:
        level = "soon"
    else:
        level = "ok"
    return {
        **row,
        "per_day": round(per_day, 1),
        "days_left": None if days_left is None else round(days_left, 1),
        "level": level,
        "level_label": LEVEL_LABEL[level],
    }


def load_items(item_id: int | None = None) -> list[dict]:
    since = utcnow() - timedelta(days=current_app.config["AVG_WINDOW_DAYS"])
    where, params = "", {"since": since}
    if item_id is not None:
        where, params["id"] = "AND i.id = %(id)s", item_id
    rows = query(STATUS_SQL.format(where=where), params)
    items = [with_status(r) for r in rows]
    items.sort(key=lambda r: (LEVEL_ORDER[r["level"]], r["days_left"] if r["days_left"] is not None else 1e9, r["name"]))
    return items


def load_item(item_id: int) -> dict:
    items = load_items(item_id)
    if not items:
        abort(404)
    return items[0]


def secret_fields(item: dict) -> dict:
    """店主だけが見る暗号化列を復号する。"""

    def dec(v):
        return crypto.decrypt(v, _key()) if v else ""

    return {"supplier": dec(item["supplier_enc"]), "unit_cost": dec(item["unit_cost_enc"]), "note": dec(item["note_enc"])}


def suggest_qty(item: dict) -> int:
    """発注の目安: 発注点 + 届くまでの使用見込み（1日の使用 × 届くまでの日数、切り上げ）− 在庫。0 未満は 0。"""
    need = item["threshold"] + math.ceil(item["per_day"] * item["lead_days"]) - item["stock"]
    return max(need, 0)


# ---------- 画面 ----------
@bp.get("/")
def index():
    return render_template("index.html", items=load_items())


@bp.get("/items/<int:item_id>")
def item_detail(item_id):
    item = load_item(item_id)
    moves = query(
        """SELECT m.*, u.login_id AS by_user, v.login_id AS voided_user
           FROM moves m LEFT JOIN users u ON u.id = m.user_id LEFT JOIN users v ON v.id = m.voided_by
           WHERE m.item_id = %s ORDER BY m.created_at DESC, m.id DESC LIMIT 50""",
        (item_id,),
    )
    secret = secret_fields(item) if g.user["role"] == "owner" else None
    return render_template("item.html", item=item, moves=moves, secret=secret, kind_label=KIND_LABEL)


@bp.get("/orders")
@owner_required
def orders():
    """発注が必要な品目（在庫切れ・要発注・まもなく）を仕入先ごとにまとめる。仕入先は暗号化列なので店主だけ。"""
    groups: dict[str, list[dict]] = {}
    for it in load_items():
        if it["level"] == "ok":
            continue
        supplier = secret_fields(it)["supplier"] or NO_SUPPLIER
        groups.setdefault(supplier, []).append({**it, "suggest": suggest_qty(it)})
    names = sorted(groups, key=lambda s: (s == NO_SUPPLIER, s))
    return render_template("orders.html", groups=[(s, groups[s]) for s in names])


@bp.post("/items/<int:item_id>/moves")
def add_move(item_id):
    kind = request.form.get("kind")
    note = request.form.get("note", "").strip()[:100]
    try:
        qty = int(request.form.get("qty", ""))
    except ValueError:
        flash("数量を数字で入れてください", "error")
        return redirect(url_for(".item_detail", item_id=item_id))

    conn = get_conn()
    # 同時に記録されても在庫がマイナスにならないよう、品目の行をロックしてから計算する
    if conn.execute("SELECT id FROM items WHERE id = %s AND NOT archived FOR UPDATE", (item_id,)).fetchone() is None:
        abort(404)
    stock = load_item(item_id)["stock"]
    error, delta = validate_move(kind, qty, stock)
    if error:
        flash(error, "error")
        return redirect(url_for(".item_detail", item_id=item_id))

    conn.execute(
        "INSERT INTO moves (item_id, kind, delta, note, user_id) VALUES (%s, %s, %s, %s, %s)",
        (item_id, kind, delta, note, g.user["id"]),
    )
    flash(f"{KIND_LABEL[kind]}を記録しました", "ok")
    return redirect(url_for(".item_detail", item_id=item_id))


def validate_move(kind: str | None, qty: int, stock: int) -> tuple[str | None, int]:
    if kind == "in":
        return (None, qty) if qty > 0 else ("入荷量は1以上にしてください", 0)
    if kind == "out":
        if qty <= 0:
            return "使用量は1以上にしてください", 0
        if qty > stock:
            return f"在庫（{stock}）より多くは使えません。実際の量が違うなら棚卸しで直してください", 0
        return None, -qty
    if kind == "count":
        if qty < 0:
            return "実在庫は0以上にしてください", 0
        if qty == stock:
            return "記録上の在庫と同じなので、直す必要はありません", 0
        return None, qty - stock
    return "種類が不正です", 0


@bp.post("/moves/<int:move_id>/void")
@owner_required
def void_move(move_id):
    conn = get_conn()
    move = conn.execute("SELECT * FROM moves WHERE id = %s AND voided_at IS NULL", (move_id,)).fetchone()
    if move is None:
        abort(404)
    conn.execute("SELECT id FROM items WHERE id = %s FOR UPDATE", (move["item_id"],))
    stock = load_item(move["item_id"])["stock"]
    if stock - move["delta"] < 0:
        flash("取り消すと在庫がマイナスになります。後の記録から先に取り消してください", "error")
    else:
        conn.execute("UPDATE moves SET voided_at = now(), voided_by = %s WHERE id = %s", (g.user["id"], move_id))
        flash("記録を取り消しました", "ok")
    return redirect(url_for(".item_detail", item_id=move["item_id"]))


# ---------- 品目の登録・編集（店主だけ） ----------
def parse_item_form(form) -> dict:
    name = form.get("name", "").strip()[:80]
    if not name:
        raise ValueError("品名を入れてください")
    if form.get("category") not in CATEGORIES:
        raise ValueError("区分を選んでください")
    if form.get("unit") not in UNITS:
        raise ValueError("単位を選んでください")
    try:
        threshold = int(form.get("threshold", "0") or 0)
        lead_days = int(form.get("lead_days", "3") or 3)
    except ValueError as e:
        raise ValueError("発注点・届くまでの日数は数字で入れてください") from e
    if threshold < 0 or lead_days < 0:
        raise ValueError("発注点・届くまでの日数は0以上にしてください")
    unit_cost = form.get("unit_cost", "").strip()
    if unit_cost and not unit_cost.replace(".", "", 1).isdigit():
        raise ValueError("仕入単価は数字で入れてください")

    def enc(v):
        v = v.strip()
        return crypto.encrypt(v, _key()) if v else None

    return {
        "name": name,
        "category": form["category"],
        "unit": form["unit"],
        "threshold": threshold,
        "lead_days": lead_days,
        "supplier_enc": enc(form.get("supplier", "")[:80]),
        "unit_cost_enc": enc(unit_cost),
        "note_enc": enc(form.get("note", "")[:500]),
    }


@bp.route("/items/new", methods=["GET", "POST"])
@owner_required
def item_new():
    if request.method == "POST":
        try:
            f = parse_item_form(request.form)
        except ValueError as e:
            flash(str(e), "error")
            return render_template("item_form.html", item=None, form=request.form, categories=CATEGORIES, units=UNITS), 400
        row = query(
            """INSERT INTO items (name, category, unit, threshold, lead_days, supplier_enc, unit_cost_enc, note_enc)
               VALUES (%(name)s, %(category)s, %(unit)s, %(threshold)s, %(lead_days)s,
                       %(supplier_enc)s, %(unit_cost_enc)s, %(note_enc)s) RETURNING id""",
            f,
            one=True,
        )
        flash("品目を登録しました", "ok")
        return redirect(url_for(".item_detail", item_id=row["id"]))
    return render_template("item_form.html", item=None, form={}, categories=CATEGORIES, units=UNITS)


@bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@owner_required
def item_edit(item_id):
    item = load_item(item_id)
    if request.method == "POST":
        try:
            f = parse_item_form(request.form)
        except ValueError as e:
            flash(str(e), "error")
            return render_template("item_form.html", item=item, form=request.form, categories=CATEGORIES, units=UNITS), 400
        query(
            """UPDATE items SET name = %(name)s, category = %(category)s, unit = %(unit)s,
                   threshold = %(threshold)s, lead_days = %(lead_days)s, supplier_enc = %(supplier_enc)s,
                   unit_cost_enc = %(unit_cost_enc)s, note_enc = %(note_enc)s WHERE id = %(id)s""",
            {**f, "id": item_id},
        )
        flash("品目を更新しました", "ok")
        return redirect(url_for(".item_detail", item_id=item_id))
    form = {**item, **secret_fields(item)}
    return render_template("item_form.html", item=item, form=form, categories=CATEGORIES, units=UNITS)


@bp.post("/items/<int:item_id>/archive")
@owner_required
def item_archive(item_id):
    load_item(item_id)
    query("UPDATE items SET archived = TRUE WHERE id = %s", (item_id,))
    flash("取扱終了にしました（記録は残っています）", "ok")
    return redirect(url_for(".index"))

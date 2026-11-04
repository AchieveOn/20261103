"""ログイン・権限・CSRF・Host チェック。

before_request は guard() の1本だけ。順番に意味がある: Host → ログイン → CSRF
役割: owner（店主: 品目の登録・原価/仕入先の閲覧・取消）／ staff（在庫の閲覧と入出庫の記録だけ）
"""

import hmac
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlsplit

import click
from flask import Blueprint, abort, current_app, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import query

bp = Blueprint("auth", __name__)

LOGIN_ERROR = "IDまたはパスワードが違います"
LOCK_ERROR = "ログインを一時的に止めています。しばらくしてからもう一度どうぞ"
MIN_PASSWORD = 12
ROLES = ("owner", "staff")
PUBLIC_ENDPOINTS = {"auth.login", "static", "healthz"}
# 存在しない ID でも同じ重さの照合をする（応答時間で ID の有無がばれないように）
DUMMY_HASH = generate_password_hash(secrets.token_hex(16), method="scrypt")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------- 門番 ----------
def guard():
    return check_host() or require_login() or check_csrf()


def check_host():
    """DNS リバインディング・Host ヘッダ偽装対策。ヘルスチェックだけは素通し。"""
    if request.endpoint == "healthz":
        return None
    if request.host.rsplit(":", 1)[0] not in current_app.config["ALLOWED_HOSTS"]:
        return "Bad Host", 400
    return None


def current_user():
    uid = session.get("uid")
    if uid is None:
        return None
    user = query("SELECT id, login_id, role, session_gen, active FROM users WHERE id = %s", (uid,), one=True)
    if user is None or not user["active"] or user["session_gen"] != session.get("gen"):
        return None
    return user


def require_login():
    g.user = None
    if request.endpoint in PUBLIC_ENDPOINTS:
        return None
    g.user = current_user()
    if g.user is not None:
        return None
    return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def check_csrf():
    """書き込み（POST）は画面に埋め込んだトークンと一致しないと受け付けない。"""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    sent = request.form.get("csrf_token", "")
    expected = session.get("csrf", "")
    if not expected or not hmac.compare_digest(sent, expected):
        return "画面を読み込み直してください", 403
    return None


def owner_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None or g.user["role"] != "owner":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def safe_next(url: str | None) -> str:
    """ログイン後の移動先。自サイト内のパスだけ許す（オープンリダイレクト対策）。"""
    if not url or not url.startswith("/") or url.startswith("//") or "\\" in url:
        return "/"
    parts = urlsplit(url)
    if parts.scheme or parts.netloc:
        return "/"
    return url


# ---------- ログイン ----------
@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", login_id="", error="")

    if (resp := check_csrf()) is not None:
        return resp
    login_id = request.form.get("login_id", "").strip()
    password = request.form.get("password", "")
    if not login_id or not password:
        return render_template("login.html", login_id=login_id, error="IDとパスワードを入れてください"), 400

    fail = query("SELECT * FROM login_failures WHERE login_id = %s", (login_id,), one=True)
    if fail and fail["locked_until"] and fail["locked_until"] > utcnow():
        return render_template("login.html", login_id=login_id, error=LOCK_ERROR), 429

    user = query("SELECT * FROM users WHERE login_id = %s", (login_id,), one=True)
    ok = check_password_hash(user["password_hash"] if user else DUMMY_HASH, password)
    if not (user and ok and user["active"]):
        record_failure(login_id, fail)
        return render_template("login.html", login_id=login_id, error=LOGIN_ERROR), 401

    query("DELETE FROM login_failures WHERE login_id = %s", (login_id,))
    session.clear()   # セッション固定攻撃対策
    session["uid"] = user["id"]
    session["gen"] = user["session_gen"]
    session.permanent = True
    return redirect(safe_next(request.args.get("next")))


def record_failure(login_id: str, fail) -> None:
    """失敗を数え、規定回数続いたら一定時間ロック。ロック明けは数え直し。"""
    cfg = current_app.config
    count = 1 if fail is None or fail["locked_until"] else fail["count"] + 1
    locked = utcnow() + timedelta(minutes=cfg["LOCK_MINUTES"]) if count >= cfg["MAX_LOGIN_FAILURES"] else None
    query(
        "INSERT INTO login_failures (login_id, count, locked_until) VALUES (%s, %s, %s) "
        "ON CONFLICT (login_id) DO UPDATE SET count = EXCLUDED.count, locked_until = EXCLUDED.locked_until",
        (login_id, count, locked),
    )


@bp.post("/logout")
def logout():
    if g.user is not None:
        query("UPDATE users SET session_gen = session_gen + 1 WHERE id = %s", (g.user["id"],))
    session.clear()
    return redirect(url_for("auth.login"))


# ---------- ユーザー登録（CLI だけ。画面からは作れない） ----------
def upsert_user(login_id: str, password: str, role: str) -> None:
    login_id = (login_id or "").strip()
    if not login_id:
        raise ValueError("IDを入れてください")
    if role not in ROLES:
        raise ValueError(f"役割は {' / '.join(ROLES)} のどちらかです")
    if len(password or "") < MIN_PASSWORD:
        raise ValueError(f"パスワードは{MIN_PASSWORD}文字以上にしてください")
    query(
        "INSERT INTO users (login_id, password_hash, role) VALUES (%s, %s, %s) "
        "ON CONFLICT (login_id) DO UPDATE SET password_hash = EXCLUDED.password_hash, "
        "role = EXCLUDED.role, active = TRUE, session_gen = users.session_gen + 1",
        (login_id, generate_password_hash(password, method="scrypt"), role),
    )


@bp.cli.command("set-user")
@click.argument("login_id")
@click.option("--role", type=click.Choice(ROLES), default="staff", show_default=True)
def set_user_command(login_id, role):
    """ユーザーを登録/パスワード変更する: flask --app app auth set-user <ID> --role owner"""
    password = click.prompt("パスワード", hide_input=True, confirmation_prompt="もう一度")
    try:
        upsert_user(login_id, password, role)
    except ValueError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"「{login_id}」（{role}）を登録しました")


@bp.cli.command("disable-user")
@click.argument("login_id")
def disable_user_command(login_id):
    """退職者などを無効化する（ログイン中のセッションも即無効）。"""
    query("UPDATE users SET active = FALSE, session_gen = session_gen + 1 WHERE login_id = %s", (login_id,))
    click.echo(f"「{login_id}」を無効にしました")

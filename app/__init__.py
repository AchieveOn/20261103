"""喫茶店の在庫管理（フロント=Jinja テンプレート / アプリサーバー=Flask on Render / DB=Neon）。"""

from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from . import auth, db, inventory
from .config import Config

JST = ZoneInfo("Asia/Tokyo")

# 外部の CDN・インラインスクリプトを一切使わない前提の CSP
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "form-action 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'")


def create_app(config: type[Config] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config or Config)
    check_config(app)

    # Render はリバースプロキシの後ろ。X-Forwarded-* を1段だけ信用する
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(inventory.bp)
    app.before_request(auth.guard)
    app.jinja_env.globals["csrf_token"] = auth.csrf_token
    app.jinja_env.filters["jst"] = lambda dt: dt.astimezone(JST).strftime("%m/%d %H:%M")

    @app.after_request
    def security_headers(resp):
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Cache-Control"] = "no-store"   # 在庫・原価をブラウザや共有端末に残さない
        if app.config["SESSION_COOKIE_SECURE"]:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return resp

    @app.get("/healthz", endpoint="healthz")
    def healthz():
        """Render のヘルスチェック用（ログイン不要・中身は返さない）。"""
        status = db.ping()
        code = 503 if status == "error" else 200
        return jsonify(status="ok" if code == 200 else "ng", db=status), code

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("error.html", message="この操作は店主だけができます"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", message="見つかりません"), 404

    return app


def check_config(app: Flask) -> None:
    """本番で秘密情報の設定漏れがあれば起動させない（弱い既定値で動かさない）。"""
    if app.config["TESTING"]:
        return
    missing = [k for k in ("SECRET_KEY", "DATABASE_URL", "APP_ENCRYPTION_KEY") if not app.config[k]]
    if missing:
        raise RuntimeError(f"環境変数が未設定です: {', '.join(missing)}（.env.example を参照）")

"""CLAUDE.md の恒常ルールのうち、コードと文書を読めば機械的に判定できるものをテストにする。

DB に接続しない（TEST_DATABASE_URL が無くても動く）。対応表は docs/GUARDRAILS.md。
"""

import re
from pathlib import Path

from app import create_app
from app.config import TestConfig

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / "app/schema.sql").read_text(encoding="utf-8")
ROLES = (ROOT / "docs/neon/roles.sql").read_text(encoding="utf-8")
ARCH = (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")


def strip_sql_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def tables() -> dict[str, list[str]]:
    """schema.sql の 表名 → 列名。"""
    out = {}
    for name, body in re.findall(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", strip_sql_comments(SCHEMA), re.S):
        out[name] = [line.split()[0] for line in body.splitlines() if line.strip()]
    return out


def grants(role: str) -> dict[str, set[str]]:
    """roles.sql で role に与えた 表名 → 権限（ON ALL ... IN SCHEMA と SCHEMA への GRANT は除く）。"""
    out: dict[str, set[str]] = {}
    for privs, objs, roles in re.findall(r"GRANT ([\w, ]+?) ON ([\w, ]+?) TO ([\w, ]+?);", strip_sql_comments(ROLES)):
        if role not in [r.strip() for r in roles.split(",")] or objs.startswith(("ALL ", "SCHEMA ")):
            continue
        for t in objs.split(","):
            out.setdefault(t.strip(), set()).update(p.strip() for p in privs.split(","))
    return out


# ===== 在庫は記録の合計・記録は消さない =====


def test_no_stock_column():
    """在庫数の列を作らない（在庫 = moves.delta の合計）。"""
    for table, cols in tables().items():
        bad = [c for c in cols if re.search(r"stock|qty|quantity|on_hand|balance", c)]
        assert not bad, f"{table} に在庫数らしき列: {bad}"


def test_app_never_deletes_or_drops_records():
    for path in [*ROOT.glob("app/**/*.py"), *ROOT.glob("backup/**/*.py")]:
        src = path.read_text(encoding="utf-8")
        hits = re.findall(r"\b(DELETE\s+FROM\s+(?!login_failures\b)\w+|TRUNCATE|DROP\s+TABLE)\b", src, re.I)
        assert not hits, f"{path.relative_to(ROOT)}: {hits}"


# ===== DDL と DB 権限を揃える =====


def test_every_table_is_granted_to_app_rw():
    granted = grants("app_rw")
    missing = [t for t in tables() if t not in granted]
    assert not missing, f"roles.sql で app_rw に権限が無い表（本番で permission denied になる）: {missing}"


def test_app_rw_delete_only_on_login_failures():
    with_delete = {t for t, p in grants("app_rw").items() if "DELETE" in p or "TRUNCATE" in p or "ALL" in p}
    assert with_delete == {"login_failures"}


def test_backup_ro_is_read_only():
    text = strip_sql_comments(ROLES)
    for privs, _ in re.findall(r"GRANT ([\w, ]+?) ON (.+?) TO [\w, ]*backup_ro", text):
        assert set(p.strip() for p in privs.split(",")) <= {"SELECT", "USAGE"}, privs


# ===== 秘匿情報は暗号化列だけ =====


def test_secret_columns_are_encrypted():
    """品目の仕入先・単価・メモは *_enc 列（暗号文）にだけ置く。"""
    plain = [c for c in tables()["items"] if re.search(r"supplier|cost|price|note", c) and not c.endswith("_enc")]
    assert not plain, f"items に平文の秘匿列: {plain}"


# ===== 画面: 外部読み込み・インライン JS なし（CSP と揃える） =====


def test_templates_have_no_inline_js_or_external_resources():
    for path in ROOT.glob("app/templates/*.html"):
        html = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html, re.I), f"{rel}: インライン <script>"
        assert not re.search(r"\son[a-z]+\s*=", html, re.I), f"{rel}: onclick などのイベント属性"
        assert not re.search(r"""(src|href)\s*=\s*["'](https?:)?//""", html, re.I), f"{rel}: 外部の読み込み"


# ===== 文書と実装のズレ（ARCHITECTURE.md の表と図） =====


def documented_routes() -> set[str]:
    rows = [line for line in ARCH.splitlines() if line.startswith("| `app/")]
    return {tok for row in rows for tok in re.findall(r"`(/[^`]*)`", row)}


def test_routes_match_architecture_doc():
    app = create_app(TestConfig)
    actual = {re.sub(r"<[^>]+>", "<id>", r.rule) for r in app.url_map.iter_rules() if r.endpoint != "static"}
    documented = documented_routes()
    assert actual - documented == set(), f"ARCHITECTURE.md の表に無いルート（文書に足す）: {actual - documented}"
    assert documented - actual == set(), f"実装に無いルートが文書にある（文書から消す）: {documented - actual}"


def test_every_app_module_is_in_architecture_doc():
    missing = [p.name for p in ROOT.glob("app/*.py") if f"`app/{p.name}`" not in ARCH]
    assert not missing, f"ARCHITECTURE.md の表に無いファイル: {missing}"


def test_app_diagram_names_every_module():
    """「アプリの中身」の図に、画面を持つモジュール（Blueprint）が全部いる。"""
    diagram = ARCH.split("## アプリの中身", 1)[1].split("```", 2)[1]
    for bp in create_app(TestConfig).blueprints:
        assert f"{bp}.py" in diagram, f"アプリの中身の図に {bp}.py が無い"

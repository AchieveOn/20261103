"""守りのテストが本当に効いているかを確かめる（わざと壊して RED になることを見る）。

使い方: TEST_DATABASE_URL=... .venv/bin/python tests/mutation_check.py
各行は (ファイル, 壊す前, 壊した後, 説明)。守りを足したらここに1行足す。
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MUTATIONS = [
    (
        "app/auth.py",
        "return check_host() or require_login() or check_csrf()",
        "return check_host() or require_login()",
        "CSRF チェックを外す",
    ),
    (
        "app/auth.py",
        'if request.host.rsplit(":", 1)[0] not in current_app.config["ALLOWED_HOSTS"]:',
        "if False:",
        "Host チェックを外す",
    ),
    ("app/auth.py", 'user["session_gen"] != session.get("gen")', "False", "ログアウト後の古い Cookie を通す"),
    ("app/auth.py", 'if fail and fail["locked_until"] and fail["locked_until"] > utcnow():', "if False:", "ログインロックを外す"),
    (
        "app/inventory.py",
        '@bp.post("/moves/<int:move_id>/void")\n@owner_required',
        '@bp.post("/moves/<int:move_id>/void")',
        "取消を staff にも許す",
    ),
    ("app/inventory.py", "return crypto.encrypt(v, _key()) if v else None", "return v or None", "暗号化せずに保存"),
    ("app/inventory.py", 'if g.user["role"] == "owner" else None', "", "staff に原価・仕入先を見せる"),
    ("app/inventory.py", "if qty > stock:", "if False:", "在庫より多く使えてしまう"),
    ("app/inventory.py", "WHERE m.voided_at IS NULL), 0)", "), 0)", "取消済みも在庫に数える"),
    ("app/__init__.py", 'resp.headers["Cache-Control"] = "no-store"', "pass", "キャッシュ禁止を外す"),
    ("app/inventory.py", '@bp.get("/orders")\n@owner_required', '@bp.get("/orders")', "発注リスト（仕入先）を staff に見せる"),
    # ===== ルール（tests/test_rules.py）=====
    (
        "docs/neon/roles.sql",
        "GRANT SELECT, INSERT, UPDATE ON users, items, moves TO app_rw;",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON users, items, moves TO app_rw;",
        "app_rw に DELETE を広げる",
    ),
    (
        "app/schema.sql",
        "    archived      BOOLEAN NOT NULL DEFAULT FALSE,",
        "    archived      BOOLEAN NOT NULL DEFAULT FALSE,\n    stock         INTEGER NOT NULL DEFAULT 0,",
        "在庫数の列を足す",
    ),
    ("app/templates/base.html", "</body>", "<script>alert(1)</script></body>", "インライン JS を足す"),
    ("docs/ARCHITECTURE.md", "`/moves/<id>/void` 取消（店主）、", "", "文書からルートが抜ける"),
    # ===== ガード（tests/test_guard.py ほか）=====
    (".claude/hooks/guard.py", "if ENV_IN_COMMAND.search(cmd):", "if False:", ".env を Bash から読ませる"),
    (".claude/hooks/guard.py", "if TDD_CODE.match(rel) and not tests_touched(root):", "if False:", "TDD の門を外す"),
    (
        ".claude/hooks/guard.py",
        'if rel.startswith(PROTECTED) and env.get("CLAUDE_GUARD_MAINTENANCE") != "1":',
        "if False:",
        "ガード自身の保護を外す",
    ),
    (".githooks/check_personal.py", "if email.endswith(NOREPLY):", "if True:", "コミット作者の確認を外す"),
    (
        ".github/scripts/test_guard.py",
        "return [f for f in changed if f.startswith(GUARD_PATHS)]",
        "return []",
        "PR でのガード変更の検知を外す",
    ),
]


def run_tests() -> bool:
    return (
        subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True
        ).returncode
        == 0
    )


def main() -> int:
    if not run_tests():
        print("元のコードでテストが落ちています。先に直してください")
        return 1
    survived = []
    for rel, before, after, label in MUTATIONS:
        path = ROOT / rel
        src = path.read_text(encoding="utf-8")
        if before not in src:
            print(f"?? 対象が見つからない: {label}")
            survived.append(label)
            continue
        try:
            path.write_text(src.replace(before, after, 1), encoding="utf-8")
            passed = run_tests()
        finally:
            path.write_text(src, encoding="utf-8")
        print(("NG 素通り  " if passed else "OK RED    ") + label)
        if passed:
            survived.append(label)
    print(f"\n{len(MUTATIONS) - len(survived)}/{len(MUTATIONS)} の壊し方をテストが検出")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())

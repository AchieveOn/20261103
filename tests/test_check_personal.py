"""コミット前の個人情報チェック（.githooks/check_personal.py）のテスト。

テストデータのメールアドレスは "@" を分けて書く（このファイル自体がチェックに引っかからないように）。
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_personal", ROOT / ".githooks/check_personal.py")
cp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cp)

AT = "@"


def test_noreply_author_is_ok():
    assert cp.author_problem("218185482+AchieveOn" + AT + "users.noreply.github.com") is None


def test_personal_author_is_rejected():
    assert cp.author_problem("taro" + AT + "hotmail.com")
    assert cp.author_problem("")


def test_personal_email_in_added_lines_is_reported():
    problems = cp.content_problems([("docs/a.md", "連絡先: taro" + AT + "gmail.com")], [])
    assert len(problems) == 1 and "docs/a.md" in problems[0]


def test_allowed_emails_pass():
    lines = [
        ("a.py", "u = 't" + AT + "example.com'"),
        ("b.md", "AchieveOn" + AT + "users.noreply.github.com"),
        ("c.yml", "postgresql://postgres:pw" + AT + "localhost:5432/db"),
    ]
    assert cp.content_problems(lines, []) == []


def test_denylist_hits_are_reported_without_echoing_the_word():
    problems = cp.content_problems([("app/x.html", "店名: 喫茶ヤマダ本店")], ["# コメント", "", "喫茶ヤマダ"])
    assert len(problems) == 1
    assert "喫茶ヤマダ" not in problems[0]  # 出力（AI にも見える）に本物の名前を出さない


def test_denylist_is_case_insensitive():
    assert cp.content_problems([("a.md", "by Taro Yamada")], ["taro yamada"])


def test_parse_added_lines_from_diff():
    diff = """diff --git a/docs/a.md b/docs/a.md
--- a/docs/a.md
+++ b/docs/a.md
@@ -1,0 +2,2 @@
+新しい行
+もう1行
-消した行
"""
    assert cp.added_lines(diff) == [("docs/a.md", "新しい行"), ("docs/a.md", "もう1行")]

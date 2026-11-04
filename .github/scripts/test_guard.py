"""PR の差分でテストが弱まっていないかを調べる（test-guard.yml から呼ぶ）。

検出するもの:
  - tests/ 配下のファイル削除
  - test_ 関数の数が減った
  - skip / xfail が増えた
  - mutation_check.py の壊し方リストが減った
環境変数: BASE（比較先 ref）, APPROVED（"true" なら警告だけで通す）
"""

import os
import re
import subprocess
import sys

BASE = os.environ.get("BASE", "origin/develop")
APPROVED = os.environ.get("APPROVED") == "true"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def tree_text(ref: str) -> str:
    """ref 時点の tests/ 配下の .py を全部つなげたもの。"""
    files = [f for f in git("ls-tree", "-r", "--name-only", ref, "--", "tests").split() if f.endswith(".py")]
    return "\n".join(git("show", f"{ref}:{f}") for f in files)


def count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.M))


def main() -> int:
    merge_base = git("merge-base", BASE, "HEAD").strip()
    before, after = tree_text(merge_base), tree_text("HEAD")
    problems = []

    deleted = git("diff", "--name-only", "--diff-filter=D", merge_base, "HEAD", "--", "tests").split()
    if deleted:
        problems.append(f"テストファイルが削除されています: {', '.join(deleted)}")

    checks = [
        (r"^\s*def test_", "テスト関数", lambda b, a: a < b),
        (r"pytest\.mark\.(skip|skipif|xfail)|pytest\.skip\(", "skip/xfail", lambda b, a: a > b),
        (r"^\s*\(\"app/", "mutation_check の壊し方", lambda b, a: a < b),
    ]
    for pattern, label, worse in checks:
        b, a = count(pattern, before), count(pattern, after)
        print(f"{label}: {b} → {a}")
        if worse(b, a):
            problems.append(f"{label}が {b} → {a} に変化")

    changed = git("diff", "--name-only", merge_base, "HEAD", "--", "tests").split()
    print("変更されたテスト:", ", ".join(changed) or "なし")

    if not problems:
        print("OK: テストは弱まっていません")
        return 0
    for p in problems:
        print(f"::{'warning' if APPROVED else 'error'}::{p}")
    if APPROVED:
        print("ラベル test-change-approved があるので通します")
        return 0
    print("意図した変更ならレビュー後に PR へ test-change-approved ラベルを付けてください")
    return 1


if __name__ == "__main__":
    sys.exit(main())

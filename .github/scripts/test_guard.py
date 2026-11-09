"""PR の差分でテストが弱まっていないかを調べる（test-guard.yml から呼ぶ）。

検出するもの:
  - tests/ 配下のファイル削除
  - test_ 関数の数が減った
  - skip / xfail が増えた
  - mutation_check.py の壊し方リストが減った
  - ガード（Claude Code の hooks・Git hooks・CI の設定とスクリプト）が変更された
環境変数: BASE（比較先 ref）, APPROVED（"true" なら警告だけで通す）
"""

import ast
import os
import re
import subprocess
import sys

BASE = os.environ.get("BASE", "origin/develop")
APPROVED = os.environ.get("APPROVED") == "true"
MUTATION_FILE = "tests/mutation_check.py"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


# 変更されたら人の承認（ラベル）が要るファイル。.claude/hooks/guard.py の PROTECTED と揃える
GUARD_PATHS = (".claude/", ".githooks/", ".github/workflows/", ".github/scripts/")


def guard_files(changed: list[str]) -> list[str]:
    return [f for f in changed if f.startswith(GUARD_PATHS)]


def tree_text(ref: str) -> str:
    """ref 時点の tests/ 配下の .py を全部つなげたもの。"""
    files = [f for f in git("ls-tree", "-r", "--name-only", ref, "--", "tests").split() if f.endswith(".py")]
    return "\n".join(git("show", f"{ref}:{f}") for f in files)


def count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.M))


def mutation_count(ref: str) -> int:
    """ref 時点の MUTATIONS リストの要素数。

    行の形で数えると、整形で1件が複数行に折り返されたときに数え漏れる（実際に 10 件を 7 件と数えた）。
    ファイルが無い・読めない・リストが見つからないときは 0（＝減ったと判定される側に倒す）。
    """
    try:
        src = git("show", f"{ref}:{MUTATION_FILE}")
        tree = ast.parse(src)
    except (subprocess.CalledProcessError, SyntaxError):
        return 0
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == "MUTATIONS" for t in targets):
            if isinstance(node.value, (ast.List, ast.Tuple)):
                return len(node.value.elts)
    return 0


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
    ]
    counts = [(label, count(p, before), count(p, after), worse) for p, label, worse in checks]
    counts.append(("mutation_check の壊し方", mutation_count(merge_base), mutation_count("HEAD"), lambda b, a: a < b))
    for label, b, a, worse in counts:
        print(f"{label}: {b} → {a}")
        if worse(b, a):
            problems.append(f"{label}が {b} → {a} に変化")

    guards = guard_files(git("diff", "--name-only", merge_base, "HEAD").split())
    if guards:
        problems.append(f"ガードの設定が変更されています（人が中身を確認すること）: {', '.join(guards)}")

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

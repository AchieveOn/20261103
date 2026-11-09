#!/usr/bin/env python3
"""コミット前の個人情報チェック（pre-commit から呼ぶ）。公開リポジトリなので実名・メアドを入れない。

- コミット作者のメールが GitHub の noreply であること
- 追加した行に、許可外のメールアドレスが無いこと
- 追加した行に、.githooks/denylist.local（各自の手元だけ・コミットしない）の語が無いこと
  例: 本名・店名・学校名。1行1語、# から始まる行はコメント。該当しても語そのものは表示しない
"""

import re
import subprocess
import sys
from pathlib import Path

NOREPLY = "@users.noreply.github.com"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
ALLOWED_DOMAINS = {"users.noreply.github.com", "example.com", "example.org", "example.net"}
DENYLIST = Path(__file__).with_name("denylist.local")


def author_problem(email: str) -> str | None:
    if email.endswith(NOREPLY):
        return None
    return "コミット作者のメールが noreply ではありません: git config user.email '<ID>+<名前>@users.noreply.github.com'"


def content_problems(added: list[tuple[str, str]], denylist: list[str]) -> list[str]:
    words = [w.strip().lower() for w in denylist if w.strip() and not w.strip().startswith("#")]
    problems = []
    for path, line in added:
        for m in EMAIL.finditer(line):
            if m.group(1).lower() not in ALLOWED_DOMAINS:
                problems.append(f"{path}: 個人のメールアドレスらしきもの（{m.group(1)}）")
        lowered = line.lower()
        for i, w in enumerate(words, 1):
            if w in lowered:
                problems.append(f"{path}: denylist.local の {i} 番目の語が含まれています")
    return problems


def added_lines(diff: str) -> list[tuple[str, str]]:
    out, path = [], ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("+") and path:
            out.append((path, line[1:]))
    return out


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main() -> int:
    ident = git("var", "GIT_AUTHOR_IDENT")
    email = ident[ident.find("<") + 1 : ident.find(">")]
    problems = [p for p in [author_problem(email)] if p]
    denylist = DENYLIST.read_text(encoding="utf-8").splitlines() if DENYLIST.exists() else []
    problems += content_problems(added_lines(git("diff", "--cached", "-U0", "--no-color")), denylist)
    for p in problems:
        print(f"[personal] {p}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

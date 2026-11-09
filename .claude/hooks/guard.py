#!/usr/bin/env python3
"""Claude Code の PreToolUse フック（ハーネス側のガード）。ルールは CLAUDE.md、対応表は docs/GUARDRAILS.md。

- .env など秘密情報ファイルを AI が読む・書く・検索するのを止める（.env.example は可）
- Git hooks のすり抜け（--no-verify・core.hooksPath・SKIP_TESTS）と、main/develop への push・force push を止める
- 本番 DB（Neon）への接続と鍵の生成を止める（本番の鍵・ユーザーは本人が作る）
- ガード自身（.claude/・.githooks/・.github/workflows/・.github/scripts/）を AI が書き換えるのを止める
  変えるときは本人が .claude/settings.local.json の env に CLAUDE_GUARD_MAINTENANCE=1 を入れて起動し直す
- TDD: app/・backup/ の .py は、tests/ に変更（未コミット or develop との差分）があるときだけ編集できる
exit 2 で拒否し、stderr の理由が Claude に返る。
"""

import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import PurePath

SECRET_NAME = re.compile(r"^\.env(\..+)?$|\.(pem|key|p12)$")
ALLOWED_NAME = {".env.example"}
# 「.env」「.env.local」などの語（.env.example は除く）。コマンド文字列のどこに出ても止める
ENV_IN_COMMAND = re.compile(r"(?<![\w.-])\.env(?!\.example)(?:\.[\w.-]+)?(?![\w-])")

# .github/scripts/test_guard.py の GUARD_PATHS と揃える
PROTECTED = (".claude/", ".githooks/", ".github/workflows/", ".github/scripts/")
PROTECTED_IN_COMMAND = re.compile(r"\.claude/|\.githooks/|\.github/(workflows|scripts)/")
WRITES_IN_COMMAND = re.compile(
    r"(?<![0-9&])>|\bsed\b[^|;&]*\s-i|\btee\b|\brm\b|\bmv\b|\bcp\b|\bchmod\b|\btruncate\b|\bln\b|\bperl\b[^|;&]*\s-i"
)
TDD_CODE = re.compile(r"^(app|backup)/.+\.py$")
BASE_REFS = ("origin/develop", "develop")


def is_secret_path(path: str) -> bool:
    name = PurePath(path).name
    return name not in ALLOWED_NAME and bool(SECRET_NAME.search(name))


def relative(path: str, root: str) -> str:
    try:
        return PurePath(path).relative_to(root).as_posix()
    except ValueError:
        return PurePath(path).as_posix()


def git_lines(root: str, *args: str) -> list[str] | None:
    res = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, check=False)  # noqa: S603 S607
    return res.stdout.splitlines() if res.returncode == 0 else None


def tests_touched(root: str) -> bool:
    """tests/ に未コミットの変更があるか、develop から分かれた後にテストを変えたコミットがあるか。"""
    if git_lines(root, "status", "--porcelain", "--untracked-files=all", "--", "tests"):
        return True
    for base in BASE_REFS:
        mb = git_lines(root, "merge-base", base, "HEAD")
        if mb:
            return bool(git_lines(root, "diff", "--name-only", mb[0], "HEAD", "--", "tests"))
    return False


def check_file(tool: str, path: str, root: str, env: Mapping[str, str]) -> str | None:
    if is_secret_path(path):
        return f"{path} は秘密情報ファイルなので AI は触りません。値は本人が設定し、雛形は .env.example に書いてください。"
    if tool in {"Read", "Grep"}:
        return None
    rel = relative(path, root)
    if rel.startswith(PROTECTED) and env.get("CLAUDE_GUARD_MAINTENANCE") != "1":
        return (
            f"{rel} はガード（hooks・CI）なので AI は書き換えません。変更が必要なら内容を本人に提案し、"
            "本人が CLAUDE_GUARD_MAINTENANCE=1 で起動し直したときだけ編集します。"
        )
    if TDD_CODE.match(rel) and not tests_touched(root):
        return f"TDD: {rel} を変える前に tests/ に失敗するテストを書き、RED を確認してください（テストの変更がまだありません）。"
    return None


def check_bash(cmd: str) -> str | None:
    if re.search(r"--no-verify|\bgit\s+commit\b[^;&|]*\s-n\b|core\.hooksPath|\bSKIP_TESTS=", cmd):
        return "Git hooks（GitFlow・秘密情報チェック・テスト）を飛ばす・外すのは禁止です。"
    # git push [オプション] <remote> [<src>:]main|develop  （feature/main-menu などは対象外）
    if re.search(r"\bgit\s+push\b(?:\s+-\S+)*\s+\S+\s+(?:\S*:)?(?:refs/heads/)?(main|develop)(?=\s|$|;|&)", cmd):
        return "main/develop への直接 push は禁止です（GitFlow: PR 経由でマージ）。"
    if re.search(r"\bgit\s+push\b[^;&|]*(\s--force\b|\s--force-with-lease\b|\s-f\b|\s\+\S)", cmd):
        return "force push は禁止です（公開リポジトリの履歴を書き換えない）。"
    if ENV_IN_COMMAND.search(cmd):
        return ".env の中身を表示・コピー・読み込みしないでください（秘密情報）。"
    if "neon.tech" in cmd:
        return "本番 DB（Neon）には AI から接続しません。本番の操作は本人が行います（手順は docs/SETUP.md）。"
    if "generate_key" in cmd:
        return "鍵の生成は本人が行います（AI の出力に鍵を残さない）。手順は docs/SETUP.md。"
    if PROTECTED_IN_COMMAND.search(cmd) and WRITES_IN_COMMAND.search(cmd):
        return "ガード（.claude/・.githooks/・.github/）をコマンドで書き換えるのは禁止です。"
    return None


def check(payload: dict, env: Mapping[str, str] | None = None) -> str | None:
    env = os.environ if env is None else env
    tool = payload.get("tool_name", "")
    data = payload.get("tool_input", {}) or {}
    root = env.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()

    if tool in {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Grep"}:
        path = data.get("file_path") or data.get("notebook_path") or data.get("path") or ""
        return check_file(tool, path, root, env) if path else None
    if tool == "Bash":
        return check_bash(data.get("command", ""))
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    reason = check(payload)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

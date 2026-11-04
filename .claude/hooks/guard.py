#!/usr/bin/env python3
"""Claude Code の PreToolUse フック（ハーネス側のガード）。

- .env など秘密情報ファイルを AI が読む・書くのを止める（.env.example は可）
- git の --no-verify（Git hooks のすり抜け）と main/develop への直接 push を止める
exit 2 で拒否し、stderr の理由が Claude に返る。
"""

import json
import re
import sys
from pathlib import PurePath

SECRET_NAME = re.compile(r"^\.env(\..+)?$|\.(pem|key|p12)$")
ALLOWED_NAME = {".env.example"}


def is_secret_path(path: str) -> bool:
    name = PurePath(path).name
    return name not in ALLOWED_NAME and bool(SECRET_NAME.search(name))


def check(payload: dict) -> str | None:
    tool = payload.get("tool_name", "")
    data = payload.get("tool_input", {}) or {}

    if tool in {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit"}:
        path = data.get("file_path") or data.get("notebook_path") or ""
        if is_secret_path(path):
            return f"{path} は秘密情報ファイルなので AI は触りません。値は本人が設定し、雛形は .env.example に書いてください。"

    if tool == "Bash":
        cmd = data.get("command", "")
        if re.search(r"--no-verify|\bgit\s+commit\b[^;&|]*\s-n\b", cmd):
            return "--no-verify で Git hooks（GitFlow・秘密情報チェック）を飛ばすのは禁止です。"
        # git push [オプション] <remote> [<src>:]main|develop  （feature/main-menu などは対象外）
        if re.search(r"\bgit\s+push\b(?:\s+-\S+)*\s+\S+\s+(?:\S*:)?(?:refs/heads/)?(main|develop)(?=\s|$|;|&)", cmd):
            return "main/develop への直接 push は禁止です（GitFlow: PR 経由でマージ）。"
        if re.search(r"(cat|less|more|head|tail|bat|source|\.)\s+[^|;&]*\.env(\s|$|[^.\w])", cmd):
            return ".env の中身を表示・読み込みしないでください（秘密情報）。"
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

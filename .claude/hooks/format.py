#!/usr/bin/env python3
"""Claude Code の PostToolUse フック: AI が書いた .py を ruff format で整える（人は VS Code の保存時整形）。

整形の失敗で作業は止めない（CI の ruff format --check で止まる）。
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    path = (payload.get("tool_input") or {}).get("file_path", "")
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")
    ruff = root / ".venv/bin/ruff"
    if path.endswith(".py") and ruff.exists():
        subprocess.run([str(ruff), "format", "--quiet", path], cwd=root, check=False)  # noqa: S603
    return 0


if __name__ == "__main__":
    sys.exit(main())

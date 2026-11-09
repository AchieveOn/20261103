"""PR の検査スクリプト（.github/scripts/test_guard.py）のうち、ガード変更の検知のテスト。"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("test_guard_script", ROOT / ".github/scripts/test_guard.py")
tg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tg)


def test_guard_file_changes_are_detected():
    changed = [
        "app/inventory.py",
        ".claude/hooks/guard.py",
        ".claude/settings.json",
        ".githooks/pre-commit",
        ".github/workflows/ci.yml",
        ".github/scripts/test_guard.py",
        "docs/SETUP.md",
    ]
    assert tg.guard_files(changed) == changed[1:6]


def test_ordinary_changes_are_not_guard_changes():
    assert tg.guard_files(["app/inventory.py", "tests/test_inventory.py", ".github/dependabot.yml"]) == []

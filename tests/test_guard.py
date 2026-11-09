"""Claude Code の PreToolUse フック（.claude/hooks/guard.py）のテスト。"""

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("guard", ROOT / ".claude/hooks/guard.py")
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

PROJ = "/proj"


def bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": PROJ}


def edit(path: str, tool: str = "Edit") -> dict:
    return {"tool_name": tool, "tool_input": {"file_path": path}, "cwd": PROJ}


@pytest.fixture(autouse=True)
def tests_already_touched(monkeypatch):
    """TDD チェック以外のテストでは「テストは先に書いてある」状態にしておく。"""
    monkeypatch.setattr(guard, "tests_touched", lambda root: True)


def blocked(payload: dict, env: dict | None = None) -> bool:
    return guard.check(payload, env or {}) is not None


# ===== 秘密情報ファイル =====


@pytest.mark.parametrize("path", [f"{PROJ}/.env", f"{PROJ}/.env.production", f"{PROJ}/certs/server.key"])
def test_secret_files_cannot_be_read_or_written(path):
    assert blocked(edit(path, "Read"))
    assert blocked(edit(path, "Write"))


def test_env_example_is_allowed():
    assert not blocked(edit(f"{PROJ}/.env.example", "Read"))


@pytest.mark.parametrize(
    "cmd",
    [
        "cat .env",
        "grep KEY .env",
        "sed -n 1,5p .env",
        "awk '{print}' .env",
        "cp .env /tmp/x",
        "python3 -c \"print(open('.env').read())\"",
        "source .env && flask run",
        "cat ./config/.env.local",
    ],
)
def test_env_cannot_be_touched_from_bash(cmd):
    assert blocked(bash(cmd))


@pytest.mark.parametrize("cmd", ["cat .env.example", "git add .env.example", "ls -a", "git status --short"])
def test_harmless_bash_is_allowed(cmd):
    assert not blocked(bash(cmd))


def test_grep_tool_on_env_is_blocked():
    assert blocked({"tool_name": "Grep", "tool_input": {"pattern": "KEY", "path": f"{PROJ}/.env"}, "cwd": PROJ})
    assert not blocked({"tool_name": "Grep", "tool_input": {"pattern": "KEY", "path": f"{PROJ}/app"}, "cwd": PROJ})


# ===== Git hooks のすり抜け・GitFlow =====


@pytest.mark.parametrize(
    "cmd",
    [
        "git commit --no-verify -m x",
        "git commit -n -m x",
        "git push --no-verify origin feature/x",
        "git -c core.hooksPath=/dev/null commit -m x",
        "git config core.hooksPath .nohooks",
        "git config --unset core.hooksPath",
        "SKIP_TESTS=1 git push origin feature/x",
    ],
)
def test_hook_bypass_is_blocked(cmd):
    assert blocked(bash(cmd))


@pytest.mark.parametrize(
    "cmd",
    [
        "git push origin develop",
        "git push origin main",
        "git push -u origin HEAD:develop",
        "git push --force origin feature/x",
        "git push -f origin feature/x",
        "git push --force-with-lease origin feature/x",
    ],
)
def test_dangerous_push_is_blocked(cmd):
    assert blocked(bash(cmd))


@pytest.mark.parametrize("cmd", ["git push -u origin feature/main-menu", "git push origin feature/develop-notes"])
def test_feature_push_is_allowed(cmd):
    assert not blocked(bash(cmd))


# ===== 本番の DB・鍵は本人だけ =====


@pytest.mark.parametrize(
    "cmd",
    [
        "psql 'host=ep-x-123.ap-southeast-1.aws.neon.tech dbname=neondb user=neondb_owner'",
        "DATABASE_URL='host=ep-x.aws.neon.tech user=app_rw' flask --app app init-db",
        ".venv/bin/python -c 'from app.crypto import generate_key; print(generate_key())'",
    ],
)
def test_production_db_and_key_generation_are_blocked(cmd):
    assert blocked(bash(cmd))


def test_local_db_is_allowed():
    assert not blocked(bash("TEST_DATABASE_URL=postgresql://localhost/cafe_test .venv/bin/python -m pytest -q"))


# ===== ガード自身を AI が弱めない =====

PROTECTED = [
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".claude/hooks/guard.py",
    ".githooks/pre-commit",
    ".github/workflows/ci.yml",
    ".github/scripts/test_guard.py",
]


@pytest.mark.parametrize("rel", PROTECTED)
def test_guard_files_cannot_be_edited(rel):
    assert blocked(edit(f"{PROJ}/{rel}"))
    assert blocked(edit(f"{PROJ}/{rel}", "Write"))


@pytest.mark.parametrize("rel", PROTECTED)
def test_guard_files_editable_in_maintenance_mode(rel):
    assert not blocked(edit(f"{PROJ}/{rel}"), {"CLAUDE_GUARD_MAINTENANCE": "1"})


def test_guard_files_can_be_read():
    assert not blocked(edit(f"{PROJ}/.claude/hooks/guard.py", "Read"))
    assert not blocked(bash("cat .claude/hooks/guard.py"))
    assert not blocked(bash("python3 .claude/hooks/guard.py < payload.json 2>&1"))


@pytest.mark.parametrize(
    "cmd",
    [
        "sed -i '' 's/exit 1/exit 0/' .githooks/pre-commit",
        "echo '{}' > .claude/settings.json",
        "rm .claude/hooks/guard.py",
        "mv .github/workflows/ci.yml /tmp/",
        "cp /tmp/x.py .claude/hooks/guard.py",
        "chmod -x .githooks/pre-push",
    ],
)
def test_guard_files_cannot_be_changed_from_bash(cmd):
    assert blocked(bash(cmd))


# ===== TDD: 本番コードより先にテスト =====


def test_app_code_needs_a_test_change_first(monkeypatch):
    monkeypatch.setattr(guard, "tests_touched", lambda root: False)
    reason = guard.check(edit(f"{PROJ}/app/inventory.py"), {})
    assert reason and "テスト" in reason
    assert blocked(edit(f"{PROJ}/backup/backup_db.py", "Write"))


def test_app_code_allowed_after_test_change(monkeypatch):
    monkeypatch.setattr(guard, "tests_touched", lambda root: True)
    assert not blocked(edit(f"{PROJ}/app/inventory.py"))


def test_non_code_files_need_no_test(monkeypatch):
    monkeypatch.setattr(guard, "tests_touched", lambda root: False)
    for rel in ["app/templates/index.html", "app/static/style.css", "docs/SETUP.md", "tests/test_x.py", "LOG.md"]:
        assert not blocked(edit(f"{PROJ}/{rel}")), rel


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "develop")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_a.py").write_text("def test_a():\n    pass\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "init")
    git(tmp_path, "switch", "-q", "-c", "feature/x")
    return tmp_path


def test_tests_touched_detects_uncommitted_and_branch_changes(repo, monkeypatch):
    monkeypatch.undo()  # autouse の差し替えを外して本物を使う
    assert guard.tests_touched(str(repo)) is False

    (repo / "tests/test_b.py").write_text("def test_b():\n    pass\n")  # 未追跡の新しいテスト
    assert guard.tests_touched(str(repo)) is True

    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "RED")  # コミット済みでも develop との差分にあれば OK
    assert guard.tests_touched(str(repo)) is True

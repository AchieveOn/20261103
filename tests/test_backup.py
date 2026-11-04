import importlib.util
import re
import shutil
import subprocess
from pathlib import Path

import psycopg
import pytest
from cryptography.fernet import Fernet, InvalidToken

from .conftest import TEST_URL

spec = importlib.util.spec_from_file_location("backup_db", Path(__file__).parents[1] / "backup" / "backup_db.py")
backup_db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup_db)

PG_DUMP = shutil.which("pg_dump") or "/opt/homebrew/opt/postgresql@17/bin/pg_dump"


def test_encrypt_roundtrip_and_wrong_key():
    key = Fernet.generate_key().decode()
    token = backup_db.encrypt(b"PGDMP...", key)
    assert b"PGDMP" not in token
    assert backup_db.decrypt(token, key) == b"PGDMP..."
    with pytest.raises(InvalidToken):
        backup_db.decrypt(token, Fernet.generate_key().decode())


def test_mail_has_encrypted_attachment():
    msg = backup_db.build_mail("a@example.com", "b@example.com", "cafe_x.dump.enc", b"gAAAA-cipher")
    parts = list(msg.iter_attachments())
    assert len(parts) == 1
    assert parts[0].get_filename() == "cafe_x.dump.enc"
    assert parts[0].get_content() == b"gAAAA-cipher"


def test_mail_without_attachment_when_too_large():
    msg = backup_db.build_mail("a@example.com", "b@example.com", "f.enc", None, "上限超え")
    assert list(msg.iter_attachments()) == []
    assert "上限超え" in msg.get_content()


def test_send_is_not_called_with_out_dir(tmp_path, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("BACKUP_DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", key)
    monkeypatch.setattr(backup_db, "dump", lambda url, pg_dump="pg_dump": b"PGDMP-fake")
    monkeypatch.setattr(backup_db, "send", lambda *a: pytest.fail("メールを送ってはいけない"))
    assert backup_db.run_backup(str(tmp_path)) == 0
    (f,) = tmp_path.iterdir()
    assert backup_db.decrypt(f.read_bytes(), key) == b"PGDMP-fake"


def test_dump_error_hides_url():
    with pytest.raises(RuntimeError) as e:
        backup_db.dump("postgresql://user:SECRETPW@127.0.0.1:1/x", PG_DUMP)  # betterleaks:allow
    assert "SECRETPW" not in str(e.value)


@pytest.mark.skipif(not TEST_URL or not Path(PG_DUMP).exists(), reason="pg_dump か TEST_DATABASE_URL がない")
def test_real_dump_restorable(app):
    # 例: "pg_dump (PostgreSQL) 17.11 (Homebrew)"
    version = subprocess.run([PG_DUMP, "--version"], capture_output=True, text=True).stdout
    client_major = int(re.search(r"\) (\d+)", version).group(1))
    with psycopg.connect(TEST_URL) as conn:
        server_major = int(conn.execute("SHOW server_version_num").fetchone()[0]) // 10000
    if client_major < server_major:
        pytest.skip(f"pg_dump {client_major} はサーバー {server_major} より古い")
    raw = backup_db.dump(TEST_URL, PG_DUMP)
    assert raw.startswith(b"PGDMP")
    listing = subprocess.run(
        [str(Path(PG_DUMP).with_name("pg_restore")), "--list"], input=raw, capture_output=True, check=True
    ).stdout.decode()
    assert "TABLE" in listing and "items" in listing

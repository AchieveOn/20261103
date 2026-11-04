"""Neon のバックアップ: pg_dump → Fernet で暗号化 → Gmail で自分宛てに送る。

Render の Cron Job（backup/Dockerfile）から毎日実行する。
  python backup_db.py                 # ダンプして暗号化し、メールで送る
  python backup_db.py --out DIR       # メールせず DIR に暗号化ファイルを保存（手元での確認用）
  python backup_db.py decrypt F.enc > F.dump   # 復号（復元は pg_restore -d <URL> F.dump）

環境変数: BACKUP_DATABASE_URL（読み取り専用ロール backup_ro）, BACKUP_ENCRYPTION_KEY,
          GMAIL_USER, GMAIL_APP_PASSWORD, BACKUP_MAIL_TO, PG_DUMP（省略時 pg_dump）
"""

import argparse
import os
import smtplib
import subprocess
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet

MAX_ATTACH = 20 * 1024 * 1024   # Gmail の添付上限 25MB（エンコード後）に余裕を持たせる
JST = ZoneInfo("Asia/Tokyo")


def env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        sys.exit(f"環境変数 {name} が未設定です")
    return value


def dump(url: str, pg_dump: str = "pg_dump") -> bytes:
    """custom 形式（圧縮済み・pg_restore で戻せる）。所有者・権限は含めない。"""
    res = subprocess.run([pg_dump, "--format=custom", "--no-owner", "--no-privileges", "--dbname", url],
                         capture_output=True, check=False)
    if res.returncode != 0:
        # URL（パスワード入り）を出さないよう、stderr だけを返す
        raise RuntimeError("pg_dump failed: " + res.stderr.decode(errors="replace").strip())
    return res.stdout


def encrypt(data: bytes, key: str) -> bytes:
    return Fernet(key).encrypt(data)


def decrypt(token: bytes, key: str) -> bytes:
    return Fernet(key).decrypt(token)


def build_mail(sender: str, to: str, filename: str, payload: bytes | None, note: str = "") -> EmailMessage:
    msg = EmailMessage()
    msg["From"], msg["To"] = sender, to
    msg["Subject"] = f"[喫茶在庫] DBバックアップ {filename}"
    body = [f"ファイル: {filename}", "暗号化済み（Fernet）。復号: python backup_db.py decrypt <file>"]
    if note:
        body.insert(0, note)
    msg.set_content("\n".join(body))
    if payload is not None:
        msg.add_attachment(payload, maintype="application", subtype="octet-stream", filename=filename)
    return msg


def send(msg: EmailMessage, user: str, app_password: str) -> None:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        smtp.login(user, app_password)
        smtp.send_message(msg)


def run_backup(out_dir: str | None) -> int:
    stamp = datetime.now(JST).strftime("%Y%m%d_%H%M")
    filename = f"cafe_{stamp}.dump.enc"
    payload = encrypt(dump(env("BACKUP_DATABASE_URL"), os.environ.get("PG_DUMP", "pg_dump")),
                      env("BACKUP_ENCRYPTION_KEY"))

    if out_dir:
        path = Path(out_dir) / filename
        path.write_bytes(payload)
        print(f"保存しました: {path}（{len(payload):,} bytes）")
        return 0

    user, to = env("GMAIL_USER"), env("BACKUP_MAIL_TO")
    if len(payload) > MAX_ATTACH:
        note = f"※ バックアップが {len(payload):,} bytes で添付上限を超えたため添付していません。保存先の見直しが必要です。"
        send(build_mail(user, to, filename, None, note), user, env("GMAIL_APP_PASSWORD"))
        print(note, file=sys.stderr)
        return 1
    send(build_mail(user, to, filename, payload), user, env("GMAIL_APP_PASSWORD"))
    print(f"送信しました: {filename}（{len(payload):,} bytes）")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", default="backup", choices=["backup", "decrypt"])
    parser.add_argument("file", nargs="?")
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.command == "decrypt":
        if not args.file:
            parser.error("decrypt にはファイルを指定してください")
        sys.stdout.buffer.write(decrypt(Path(args.file).read_bytes(), env("BACKUP_ENCRYPTION_KEY")))
        return 0
    return run_backup(args.out)


if __name__ == "__main__":
    sys.exit(main())

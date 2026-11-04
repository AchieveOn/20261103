"""設定は環境変数だけから読む（秘密情報をコードに書かない）。

ローカルでは .env を python-dotenv で読み込み、Render では Dashboard の環境変数を使う。
"""

import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _hosts(value: str) -> set[str]:
    return {h.strip() for h in value.split(",") if h.strip()}


class Config:
    TESTING = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    APP_ENCRYPTION_KEY = os.environ.get("APP_ENCRYPTION_KEY", "")
    # Render では <サービス名>.onrender.com を足す（独自ドメインも同様）
    ALLOWED_HOSTS = _hosts(os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1"))

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1") == "1"  # ローカルの http では 0
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    MAX_LOGIN_FAILURES = 5
    LOCK_MINUTES = 15
    AVG_WINDOW_DAYS = 14  # 1日あたりの使用量は直近14日の平均


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"  # noqa: S105  betterleaks:allow（テスト専用のダミー値）
    DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
    APP_ENCRYPTION_KEY = ""  # conftest で毎回生成する
    ALLOWED_HOSTS = {"localhost"}
    SESSION_COOKIE_SECURE = False

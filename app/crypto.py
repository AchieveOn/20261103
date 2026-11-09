"""アプリ側の暗号化・復号（Fernet = AES-128-CBC + HMAC-SHA256 の認証付き暗号）。

Neon 自体も保存時暗号化(AES-256)・通信 TLS だが、個人情報など特に守りたい列は
アプリで暗号化してから保存する（DB が漏れても鍵がなければ読めない）。

鍵の生成:  python -c "from app.crypto import generate_key; print(generate_key())"
"""

import os

from cryptography.fernet import Fernet, InvalidToken

__all__ = ["encrypt", "decrypt", "generate_key", "InvalidToken"]


def _fernet(key: str | None = None) -> Fernet:
    key = key or os.environ.get("APP_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("APP_ENCRYPTION_KEY が未設定です")
    return Fernet(key)


def encrypt(plaintext: str, key: str | None = None) -> str:
    return _fernet(key).encrypt(plaintext.encode()).decode()


def decrypt(token: str, key: str | None = None) -> str:
    """改ざん・鍵違いのときは InvalidToken を投げる。"""
    return _fernet(key).decrypt(token.encode()).decode()


def generate_key() -> str:
    return Fernet.generate_key().decode()


if __name__ == "__main__":
    print(generate_key())

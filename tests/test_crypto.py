import pytest

from app.crypto import InvalidToken, decrypt, encrypt, generate_key


def test_roundtrip():
    key = generate_key()
    token = encrypt("山田 太郎", key)
    assert token != "山田 太郎"
    assert decrypt(token, key) == "山田 太郎"


def test_wrong_key_rejected():
    token = encrypt("secret", generate_key())
    with pytest.raises(InvalidToken):
        decrypt(token, generate_key())


def test_tampered_token_rejected():
    key = generate_key()
    token = encrypt("secret", key)
    tampered = token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1]
    with pytest.raises(InvalidToken):
        decrypt(tampered, key)


def test_missing_key(monkeypatch):
    monkeypatch.delenv("APP_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError):
        encrypt("x")

"""AES-256-GCM secret encoding validation."""
import base64
import pytest

from app.core.crypto import encrypt_value, decrypt_value


KEY = base64.b64encode(bytes(range(32))).decode("ascii")


def test_encryption_roundtrip_and_random_nonce():
    first = encrypt_value("sensitive-value", KEY)
    second = encrypt_value("sensitive-value", KEY)
    assert first != second
    assert decrypt_value(first, KEY) == "sensitive-value"
    assert decrypt_value(second, KEY) == "sensitive-value"


@pytest.mark.parametrize("bad", ["!", "", "YQ==", base64.b64encode(bytes(27)).decode("ascii")])
def test_invalid_ciphertext_rejected(bad):
    with pytest.raises((ValueError, Exception)):
        decrypt_value(bad, KEY)


def test_tampered_ciphertext_rejected():
    cipher = bytearray(base64.b64decode(encrypt_value("private", KEY)))
    cipher[-1] ^= 1
    with pytest.raises(Exception):
        decrypt_value(base64.b64encode(cipher).decode("ascii"), KEY)

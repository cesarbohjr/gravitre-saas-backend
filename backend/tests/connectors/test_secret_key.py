from __future__ import annotations

import base64

import pytest
from cryptography.fernet import Fernet

from app.connectors.crypto import decrypt_secret, encrypt_secret
from app.connectors.secret_key import fernet_key_bytes, validate_connector_secrets_encryption_key


def test_validate_64_hex_key():
    hex_key = "a" * 64
    assert validate_connector_secrets_encryption_key(hex_key) == hex_key


def test_reject_invalid_key():
    with pytest.raises(ValueError, match="64-character hexadecimal"):
        validate_connector_secrets_encryption_key("not-a-valid-key")


def test_hex_key_round_trip_fernet():
    hex_key = Fernet.generate_key().decode()
    raw = base64.urlsafe_b64decode(hex_key.encode())
    hex_from_fernet = raw.hex()
    assert len(hex_from_fernet) == 64
    plaintext = "oauth-token-secret"
    ciphertext = encrypt_secret(plaintext, hex_from_fernet)
    assert decrypt_secret(ciphertext, hex_from_fernet) == plaintext


def test_fernet_key_bytes_from_hex():
    hex_key = "b" * 64
    material = fernet_key_bytes(hex_key)
    assert len(base64.urlsafe_b64decode(material)) == 32

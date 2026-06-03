"""IN-00: Fernet encryption for connector secrets (key material: 64-char hex or legacy Fernet)."""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.connectors.secret_key import fernet_key_bytes


def _make_fernet(key_str: str) -> Fernet:
    """Create Fernet from CONNECTOR_SECRETS_ENCRYPTION_KEY (64 hex or legacy Fernet string)."""
    if not (key_str or "").strip():
        raise ValueError("connector_secrets_encryption_key is required")
    return Fernet(fernet_key_bytes(key_str))


def encrypt_secret(plaintext: str, encryption_key: str) -> str:
    """Encrypt plaintext; return base64 ciphertext."""
    f = _make_fernet(encryption_key)
    return f.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str, encryption_key: str) -> str:
    """Decrypt ciphertext; return plaintext."""
    f = _make_fernet(encryption_key)
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError("Invalid or corrupted secret")


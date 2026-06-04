"""IN-00: Fernet encryption for connector secrets."""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


def _make_fernet(key_str: str) -> Fernet:
    """Create Fernet from env key. Must be Fernet.generate_key() output."""
    key_str = (key_str or "").strip()
    if not key_str:
        raise ValueError("connector_secrets_encryption_key is required")
    return Fernet(key_str.encode())


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


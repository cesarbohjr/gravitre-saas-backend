"""Phase 15: AES-256-GCM utilities for config secrets."""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _load_key(key: str) -> bytes:
    raw = (key or "").strip()
    if not raw:
        raise ValueError("ENCRYPTION_KEY is required")
    try:
        decoded = base64.b64decode(raw)
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    if len(raw.encode("utf-8")) == 32:
        return raw.encode("utf-8")
    raise ValueError("ENCRYPTION_KEY must be 32 bytes or base64-encoded 32 bytes")


def encrypt_value(plaintext: str, key: str) -> str:
    aes = AESGCM(_load_key(key))
    nonce = os.urandom(12)
    ciphertext = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_value(ciphertext: str, key: str) -> str:
    raw = base64.b64decode(ciphertext)
    nonce = raw[:12]
    data = raw[12:]
    aes = AESGCM(_load_key(key))
    return aes.decrypt(nonce, data, None).decode("utf-8")


def mask_value(value: str | None) -> str | None:
    if not value:
        return None
    tail = value[-4:] if len(value) >= 4 else value
    return f"••••••••{tail}"

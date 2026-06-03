"""CONNECTOR_SECRETS_ENCRYPTION_KEY validation and Fernet materialization."""
from __future__ import annotations

import base64
import re

from cryptography.fernet import Fernet

_HEX_64 = re.compile(r"^[a-fA-F0-9]{64}$")


def validate_connector_secrets_encryption_key(key: str) -> str:
    """
    Production key: 64-char hex (32 bytes).
    Legacy deployments may still use a Fernet.generate_key() string until rotated.
    """
    normalized = (key or "").strip()
    if not normalized:
        return normalized
    if _HEX_64.fullmatch(normalized):
        return normalized
    try:
        Fernet(normalized.encode())
    except Exception as exc:
        raise ValueError(
            "CONNECTOR_SECRETS_ENCRYPTION_KEY must be a 64-character hexadecimal string"
        ) from exc
    return normalized


def fernet_key_bytes(key_str: str) -> bytes:
    """Map env key to Fernet key bytes (hex → url-safe base64 of 32 bytes)."""
    normalized = validate_connector_secrets_encryption_key(key_str)
    if _HEX_64.fullmatch(normalized):
        return base64.urlsafe_b64encode(bytes.fromhex(normalized))
    return normalized.encode()

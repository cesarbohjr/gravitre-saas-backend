"""Encrypt enterprise settings secrets at rest (SIEM signing keys)."""
from __future__ import annotations

from app.connectors.crypto import decrypt_secret, encrypt_secret
from app.config import Settings


def encrypt_enterprise_secret(plaintext: str, settings: Settings) -> str:
    key = (settings.connector_secrets_encryption_key or "").strip()
    if not key:
        raise ValueError("connector_secrets_encryption_key is required for enterprise secrets")
    return encrypt_secret(plaintext, key)


def decrypt_enterprise_secret(ciphertext: str, settings: Settings) -> str:
    key = (settings.connector_secrets_encryption_key or "").strip()
    if not key:
        raise ValueError("connector_secrets_encryption_key is required for enterprise secrets")
    return decrypt_secret(ciphertext, key)


def resolve_siem_secret(siem_config: dict, settings: Settings) -> str | None:
    """Return plaintext SIEM secret from encrypted or legacy plaintext storage."""
    if not isinstance(siem_config, dict):
        return None
    encrypted = siem_config.get("secretEnc") or siem_config.get("secret_enc")
    if encrypted:
        try:
            return decrypt_enterprise_secret(str(encrypted), settings)
        except ValueError:
            return None
    legacy = siem_config.get("secret")
    return str(legacy).strip() if legacy else None

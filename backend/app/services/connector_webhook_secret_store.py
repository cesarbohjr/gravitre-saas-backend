"""Inbound webhook signing secrets kept in ``connectors.config``, encrypted at rest.

Salesforce, Segment and PagerDuty trigger secrets used to sit in plaintext in
``connectors.config``, a column org members can read. Each secret now lives at
``<key>_encrypted`` (Fernet, CONNECTOR_SECRETS_ENCRYPTION_KEY). Plaintext values
written before this change still verify and are sealed the next time the
connector's trigger settings are loaded (``ensure_webhook_secret``) or the
operator runs ``seal_plaintext_webhook_secrets``.

Without an encryption key (local development) values stay plaintext, matching
the previous behaviour; production settings require the key.
"""
from __future__ import annotations

import secrets
from collections.abc import Iterable
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

ENCRYPTED_SUFFIX = "_encrypted"
SECRET_KEYS: tuple[str, ...] = ("webhook_secret", "pagerduty_signing_secret", "segment_webhook_secret")


def _encryption_key(settings: Any | None) -> str:
    if settings is None:
        from app.config import get_settings

        settings = get_settings()
    return str(getattr(settings, "connector_secrets_encryption_key", "") or "").strip()


def read_secret(config: dict[str, Any] | None, key: str, settings: Any | None = None) -> str:
    """Plaintext of ``key``: the encrypted copy when present, else the legacy value."""
    cfg = config or {}
    sealed = str(cfg.get(f"{key}{ENCRYPTED_SUFFIX}") or "").strip()
    if sealed:
        enc_key = _encryption_key(settings)
        if not enc_key:
            logger.warning("connector_webhook_secret_undecryptable reason=no_key key=%s", key)
            return ""
        from app.connectors.crypto import decrypt_secret

        try:
            return decrypt_secret(sealed, enc_key).strip()
        except ValueError:
            logger.warning("connector_webhook_secret_undecryptable reason=bad_ciphertext key=%s", key)
            return ""
    return str(cfg.get(key) or "").strip()


def first_secret(config: dict[str, Any] | None, keys: Iterable[str], settings: Any | None = None) -> str:
    for key in keys:
        value = read_secret(config, key, settings)
        if value:
            return value
    return ""


def store_secret(config: dict[str, Any], key: str, value: str, settings: Any | None = None) -> None:
    """Write ``key`` encrypted (and drop any plaintext copy); plaintext without a key."""
    enc_key = _encryption_key(settings)
    if not enc_key:
        config[key] = value
        return
    from app.connectors.crypto import encrypt_secret

    config[f"{key}{ENCRYPTED_SUFFIX}"] = encrypt_secret(value, enc_key)
    config.pop(key, None)


def seal_plaintext(config: dict[str, Any], settings: Any | None = None) -> bool:
    """Encrypt every plaintext secret in ``config`` in place. True when changed."""
    if not _encryption_key(settings):
        return False
    changed = False
    for key in SECRET_KEYS:
        plain = str(config.get(key) or "").strip()
        if not plain:
            if key in config and not config.get(key):
                config.pop(key, None)
            continue
        store_secret(config, key, plain, settings)
        changed = True
    return changed


def ensure_webhook_secret(
    client: Any,
    org_id: str,
    connector_id: str,
    *,
    read_keys: tuple[str, ...],
    generate_keys: tuple[str, ...],
    settings: Any | None = None,
) -> str:
    """Return the connector's signing secret, generating one when absent.

    Any plaintext secret found is sealed in the same write.
    """
    from app.core.safe_dict import safe_normalize_stored_dict

    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise ValueError("Connector not found")
    config = safe_normalize_stored_dict(row.data[0], key="config")
    secret = first_secret(config, read_keys, settings)
    changed = seal_plaintext(config, settings)
    if not secret:
        secret = secrets.token_hex(32)
        for key in generate_keys:
            store_secret(config, key, secret, settings)
        changed = True
    if changed:
        client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()
    return secret


def seal_plaintext_webhook_secrets(client: Any, settings: Any | None = None, *, dry_run: bool = True) -> dict[str, int]:
    """Operator backfill: seal plaintext trigger secrets on every connector.

    Returns counts only; never logs or returns a secret value.
    """
    from app.core.safe_dict import safe_normalize_stored_dict

    if not _encryption_key(settings):
        raise ValueError("CONNECTOR_SECRETS_ENCRYPTION_KEY is required to seal webhook secrets")
    scanned = sealed = 0
    page, size = 0, 500
    while True:
        rows = (
            client.table("connectors")
            .select("id,org_id,config")
            .order("id")
            .range(page * size, page * size + size - 1)
            .execute()
        ).data or []
        for row in rows:
            scanned += 1
            config = safe_normalize_stored_dict(row, key="config")
            if not any(str(config.get(k) or "").strip() for k in SECRET_KEYS):
                continue
            sealed += 1
            if dry_run:
                continue
            seal_plaintext(config, settings)
            client.table("connectors").update({"config": config}).eq("id", row["id"]).eq(
                "org_id", row["org_id"]
            ).execute()
        if len(rows) < size:
            break
        page += 1
    return {"scanned": scanned, "with_plaintext": sealed, "sealed": 0 if dry_run else sealed}

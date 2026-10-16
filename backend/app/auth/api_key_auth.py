"""Org-scoped API key validation for external/integration access.

Keys are issued via POST /api/org/{org_id}/api-keys (admin only).
External callers present the key in the Authorization header:

    Authorization: Bearer grav_live_<random>

or as:

    X-Gravitre-Key: grav_live_<random>

The raw key is SHA-256-hashed and looked up in public.org_api_keys.
On a hit the key's org_id, scopes and created_by are returned so the
FastAPI dependency can inject org context without a Supabase JWT.

Security properties:
- The raw key is never stored; only its SHA-256 hex digest is.
- Revoked keys (revoked_at IS NOT NULL) are rejected by the DB index.
- Expired keys are rejected in Python after the DB row is loaded.
- Timing-safe comparison is not needed because the hash is public-key-size
  and the lookup is in an indexed column (exact match, not iteration).
- last_used_at is updated asynchronously to avoid adding a write to every
  hot-path request; callers can opt in with update_last_used=True.
"""
from __future__ import annotations

import hashlib
import secrets
import string
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_KEY_PREFIX_LIVE = "grav_live_"
_KEY_PREFIX_TEST = "grav_test_"
_KEY_BODY_CHARS = string.ascii_letters + string.digits
_KEY_BODY_LEN = 40   # 40 random alphanumeric chars → ~238 bits of entropy
_DISPLAY_PREFIX_LEN = 12   # chars shown in the list endpoint (prefix + first 2 body chars)

VALID_SCOPES: frozenset[str] = frozenset({
    "chat:read",
    "chat:write",
    "connector:read",
    "knowledge:read",
    "workflow:read",
    "workflow:write",
    "billing:read",
})


def generate_api_key(*, test: bool = False) -> tuple[str, str, str]:
    """Return (raw_key, key_prefix_display, key_hash).

    raw_key         — the key shown once to the user; starts grav_live_/grav_test_
    key_prefix      — first _DISPLAY_PREFIX_LEN chars; safe to store and display
    key_hash        — SHA-256 hex of raw_key; stored in the DB
    """
    prefix = _KEY_PREFIX_TEST if test else _KEY_PREFIX_LIVE
    body = "".join(secrets.choice(_KEY_BODY_CHARS) for _ in range(_KEY_BODY_LEN))
    raw_key = f"{prefix}{body}"
    key_prefix = raw_key[:_DISPLAY_PREFIX_LEN]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_prefix, key_hash


def hash_api_key(raw_key: str) -> str:
    """Hash a raw key the same way generate_api_key does."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def extract_raw_key(authorization: str | None, x_gravitre_key: str | None) -> str | None:
    """Pull the raw key from request headers, or None if not present."""
    if x_gravitre_key:
        return x_gravitre_key.strip()
    if authorization:
        parts = authorization.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            candidate = parts[1].strip()
            if candidate.startswith((_KEY_PREFIX_LIVE, _KEY_PREFIX_TEST)):
                return candidate
    return None


def validate_scopes(requested: list[str]) -> list[str]:
    """Return the validated scope list or raise ValueError on unknown scopes."""
    unknown = [s for s in requested if s not in VALID_SCOPES]
    if unknown:
        raise ValueError(f"Unknown scopes: {unknown}. Valid scopes: {sorted(VALID_SCOPES)}")
    return list(requested)


def lookup_api_key(
    client: Any,
    raw_key: str,
    *,
    update_last_used: bool = False,
) -> dict[str, Any] | None:
    """Look up an API key row by its hash.

    Returns the row dict (id, org_id, created_by, scopes, expires_at) on success.
    Returns None when:
      - key is unknown / revoked (DB index filters revoked_at IS NOT NULL rows)
      - key is expired (expires_at in the past)
      - DB lookup fails (logged, caller gets None → 401)
    """
    key_hash = hash_api_key(raw_key)
    try:
        resp = (
            client.table("org_api_keys")
            .select("id, org_id, created_by, scopes, expires_at")
            .eq("key_hash", key_hash)
            .is_("revoked_at", "null")
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("api_key_lookup_failed error=%s", exc)
        return None

    if not resp.data:
        return None

    row = resp.data[0]

    # Check expiry in Python (DB stores timestamptz; PostgREST returns ISO-8601).
    expires_at_raw = row.get("expires_at")
    if expires_at_raw:
        try:
            expires_at = datetime.fromisoformat(str(expires_at_raw).replace("Z", "+00:00"))
            if expires_at < datetime.now(timezone.utc):
                logger.info("api_key_expired id=%s org_id=%s", row.get("id"), row.get("org_id"))
                return None
        except (ValueError, TypeError):
            pass  # malformed → treat as not expired; validation elsewhere

    if update_last_used:
        try:
            client.table("org_api_keys").update({
                "last_used_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", row["id"]).execute()
        except Exception as exc:  # noqa: BLE001
            logger.debug("api_key_last_used_update_failed id=%s error=%s", row.get("id"), exc)

    return {
        "api_key_id": str(row["id"]),
        "org_id": str(row["org_id"]),
        "created_by": str(row.get("created_by") or ""),
        "scopes": list(row.get("scopes") or []),
    }

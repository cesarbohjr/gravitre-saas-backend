"""Signed OAuth state tokens (CSRF protection for connector OAuth)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from app.connectors.oauth_state_store import consume_oauth_state_jti

REQUIRED_STATE_FIELDS = ("org_id", "user_id", "connector_id", "provider", "exp", "iat", "jti", "nonce")


def new_oauth_state_nonce() -> str:
    return secrets.token_urlsafe(32)


def new_oauth_state_jti() -> str:
    return secrets.token_urlsafe(24)


def sign_oauth_state(payload: dict[str, Any], secret: str) -> str:
    if not secret:
        raise ValueError("OAuth state signing secret is required")
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_oauth_state(
    token: str,
    secret: str,
    *,
    max_age_seconds: int = 600,
    expected_provider: str | None = None,
) -> dict[str, Any]:
    if not token or "." not in token:
        raise ValueError("Invalid OAuth state")
    body, sig = token.rsplit(".", 1)
    expected_sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Invalid OAuth state signature")
    padded = body + "=" * (-len(body) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")))
    for field in REQUIRED_STATE_FIELDS:
        if not payload.get(field):
            raise ValueError(f"OAuth state missing {field}")
    if expected_provider and str(payload.get("provider")) != expected_provider:
        raise ValueError("OAuth state provider mismatch")
    exp = float(payload.get("exp") or 0)
    if exp < time.time():
        raise ValueError("OAuth state expired")
    issued = float(payload.get("iat") or exp - max_age_seconds)
    if time.time() - issued > max_age_seconds:
        raise ValueError("OAuth state expired")
    consume_oauth_state_jti(str(payload["jti"]), ttl_seconds=max_age_seconds + 60)
    return payload

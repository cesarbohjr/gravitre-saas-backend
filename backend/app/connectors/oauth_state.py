"""Signed OAuth state tokens (CSRF protection for connector OAuth)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


def sign_oauth_state(payload: dict[str, Any], secret: str) -> str:
    if not secret:
        raise ValueError("OAuth state signing secret is required")
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_oauth_state(token: str, secret: str, *, max_age_seconds: int = 600) -> dict[str, Any]:
    if not token or "." not in token:
        raise ValueError("Invalid OAuth state")
    body, sig = token.rsplit(".", 1)
    expected = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid OAuth state signature")
    padded = body + "=" * (-len(body) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")))
    exp = float(payload.get("exp") or 0)
    if exp < time.time():
        raise ValueError("OAuth state expired")
    issued = float(payload.get("iat") or exp - max_age_seconds)
    if time.time() - issued > max_age_seconds:
        raise ValueError("OAuth state expired")
    return payload

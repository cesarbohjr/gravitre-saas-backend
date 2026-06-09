"""RFC 7636 PKCE helpers for OAuth 2.0 authorization code flows."""
from __future__ import annotations

import base64
import hashlib
import secrets


def generate_code_verifier(length: int = 64) -> str:
    """Generate a cryptographically random code_verifier (43–128 chars)."""
    if length < 43 or length > 128:
        raise ValueError("code_verifier length must be between 43 and 128")
    # token_urlsafe may include '-' and '_'; strip padding
    while True:
        verifier = secrets.token_urlsafe(length)[:length]
        if 43 <= len(verifier) <= 128:
            return verifier


def code_challenge_s256(code_verifier: str) -> str:
    """S256 code_challenge = BASE64URL(SHA256(code_verifier)) without padding."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


# Dedicated (module-based) OAuth connectors that require PKCE on authorize + token exchange.
DEDICATED_PKCE_OAUTH_VENDORS: frozenset[str] = frozenset({"salesforce"})

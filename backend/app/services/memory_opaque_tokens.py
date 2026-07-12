"""STA-316 Option B — opaque Memory tokens. Never send raw PII to embedding providers."""
from __future__ import annotations

import hashlib
import hmac
import re

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_OPAQUE_TOKEN_RE = re.compile(r"^mem:(?:v1|alias:v1):[a-f0-9]{64}$")


class MemoryOpaqueTokenError(ValueError):
    """Raised when a value is unsafe to send to an embedding provider."""


def redact_mention_for_digest(text: str) -> str:
    """Normalize mention and strip email-shaped substrings before HMAC."""
    cleaned = _EMAIL_RE.sub(" ", text or "")
    return " ".join(cleaned.lower().split())[:200]


def opaque_entity_token(*, org_id: str, entity_type: str, entity_id: str, secret: str) -> str:
    material = f"{org_id}|{entity_type}|{entity_id}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), material, hashlib.sha256).hexdigest()
    return f"mem:v1:{digest}"


def opaque_alias_token(*, org_id: str, alias_normalized: str, secret: str) -> str:
    """HMAC of normalized alias — provider never sees the alias text."""
    material = f"{org_id}|alias|{alias_normalized}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), material, hashlib.sha256).hexdigest()
    return f"mem:alias:v1:{digest}"


def token_digest(token: str) -> str:
    if not _OPAQUE_TOKEN_RE.match(token or ""):
        raise MemoryOpaqueTokenError("not an opaque memory token")
    return token.rsplit(":", 1)[-1]


def assert_provider_safe_token(token: str) -> str:
    """Only opaque mem:* digests may be passed to OpenAI embeddings."""
    value = (token or "").strip()
    if not _OPAQUE_TOKEN_RE.match(value):
        raise MemoryOpaqueTokenError(
            "refusing to embed non-opaque token (raw PII / free text blocked)"
        )
    if "@" in value or " " in value:
        raise MemoryOpaqueTokenError("refusing to embed token containing raw separators")
    return value


def looks_like_raw_pii(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    if "@" in value or _EMAIL_RE.search(value):
        return True
    return False

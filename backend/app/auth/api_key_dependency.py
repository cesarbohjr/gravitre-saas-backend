"""FastAPI dependency for external API key authentication.

External callers (MCP clients, third-party integrations) present a Gravitre
API key in lieu of a Supabase JWT. This module provides:

  - `api_key_context` — a Depends()-able function that returns the API key's
    org context (org_id, scopes, api_key_id). Raises 401 if the key is absent,
    invalid, revoked, or expired.

  - `require_scope(scope)` — returns a Depends() that wraps api_key_context
    and additionally enforces that the key has a specific scope. Raises 403.

Usage:
    from app.auth.api_key_dependency import api_key_context, require_scope

    @router.post("/chat")
    async def chat(ctx = Depends(require_scope("chat:write"))):
        org_id = ctx["org_id"]
        ...
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException

from app.auth.api_key_auth import extract_raw_key, lookup_api_key
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment]

logger = get_logger(__name__)


async def api_key_context(
    authorization: Annotated[str | None, Header()] = None,
    x_gravitre_key: Annotated[str | None, Header(alias="X-Gravitre-Key")] = None,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Resolve a Gravitre API key to its org context.

    Accepts the raw key from either:
      - Authorization: Bearer grav_live_<key>
      - X-Gravitre-Key: grav_live_<key>

    Returns a dict with ``org_id``, ``api_key_id``, ``created_by``, ``scopes``.
    Raises 401 on any validation failure.
    """
    raw_key = extract_raw_key(authorization, x_gravitre_key)
    if not raw_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Pass Authorization: Bearer grav_live_<key> "
                   "or X-Gravitre-Key: <key>.",
        )

    client = shared_service_client(settings, create_client)
    ctx = lookup_api_key(client, raw_key, update_last_used=True)

    if ctx is None:
        raise HTTPException(status_code=401, detail="Invalid, revoked, or expired API key.")

    return ctx


def require_scope(scope: str):
    """Return a FastAPI dependency that enforces a specific API key scope.

    Example:
        @router.post("/messages")
        async def send(ctx = Depends(require_scope("chat:write"))): ...
    """
    async def _check(ctx: Annotated[dict, Depends(api_key_context)]) -> dict:
        if scope not in ctx.get("scopes", []):
            raise HTTPException(
                status_code=403,
                detail=f"This API key does not have the '{scope}' scope.",
            )
        return ctx

    _check.__name__ = f"require_scope_{scope.replace(':', '_')}"
    return _check

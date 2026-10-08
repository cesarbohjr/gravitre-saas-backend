"""HTTP middleware: enforce trial/subscription gating on product API paths."""
from __future__ import annotations

import asyncio
import threading
import time

from fastapi import Request
from fastapi.responses import JSONResponse

from app.auth.jwt_verify import decode_supabase_jwt
from app.billing.entitlement_service import (
    PlanRequiredError,
    assert_org_not_blocked,
    should_gate_path,
)
from app.billing.service import get_supabase_client
from app.config import get_settings
from app.services.org_membership import list_member_org_ids, pick_default_org_id


# (user_id, requested_org) -> (monotonic expiry, resolved org_id) for a recent
# "not blocked" decision. The gate runs on every product API call; before this
# it made ~4 sequential Supabase reads per request on the event loop. Only
# "allowed" is cached, briefly, so a block (or an unblock after payment) is
# never stale for more than a few seconds in the costly direction. Billing /
# membership writes drop the affected org's or user's entries immediately via
# ``forget_org`` / ``forget_user`` (called from app.core.org_state_cache).
_ALLOWED_TTL_S = 30.0
_ALLOWED_MAX_ENTRIES = 5000
_allowed_until: dict[tuple[str, str], tuple[float, str]] = {}
_allowed_lock = threading.Lock()
# Bumped on every forget_*; a check that straddles an invalidation is not cached.
_allowed_generation = 0


def _is_allowed_cached(key: tuple[str, str]) -> bool:
    entry = _allowed_until.get(key)
    return bool(entry and entry[0] > time.monotonic())


def _remember_allowed(
    key: tuple[str, str],
    org_id: str | None = None,
    generation: int | None = None,
) -> None:
    with _allowed_lock:
        if generation is not None and generation != _allowed_generation:
            return
        if len(_allowed_until) >= _ALLOWED_MAX_ENTRIES:
            _allowed_until.clear()
        _allowed_until[key] = (time.monotonic() + _ALLOWED_TTL_S, str(org_id or key[1] or ""))


def forget_org(org_id: str) -> None:
    """Drop cached "allowed" decisions that resolved to (or requested) ``org_id``."""
    oid = str(org_id or "")
    if not oid:
        return
    global _allowed_generation
    with _allowed_lock:
        _allowed_generation += 1
        for key in [k for k, (_exp, resolved) in _allowed_until.items() if resolved == oid or k[1] == oid]:
            _allowed_until.pop(key, None)


def forget_user(user_id: str) -> None:
    uid = str(user_id or "")
    if not uid:
        return
    global _allowed_generation
    with _allowed_lock:
        _allowed_generation += 1
        for key in [k for k in _allowed_until if k[0] == uid]:
            _allowed_until.pop(key, None)


def forget_all() -> None:
    global _allowed_generation
    with _allowed_lock:
        _allowed_generation += 1
        _allowed_until.clear()


def _check_billing_gate(user_id: str, requested_org: str) -> str | None:
    """Sync Supabase lookups; raises PlanRequiredError when the org is blocked.

    Returns the resolved org id (None when the user has no org).
    """
    settings = get_settings()
    client = get_supabase_client(settings)
    member_org_ids = list_member_org_ids(client, user_id)
    org_id = requested_org if requested_org in member_org_ids else pick_default_org_id(member_org_ids)
    if not org_id:
        return None
    assert_org_not_blocked(client, org_id)
    return org_id


async def billing_access_gate_middleware(request: Request, call_next):
    path = request.url.path
    if not should_gate_path(path):
        return await call_next(request)

    auth_header = request.headers.get("authorization") or ""
    if not auth_header.lower().startswith("bearer "):
        return await call_next(request)

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return await call_next(request)

    try:
        settings = get_settings()
        payload = decode_supabase_jwt(token, settings)
        user_id = str(payload.get("sub") or "")
        if not user_id:
            return await call_next(request)

        requested_org = (request.headers.get("x-org-id") or request.query_params.get("org_id") or "").strip()
        cache_key = (user_id, requested_org)
        if _is_allowed_cached(cache_key):
            return await call_next(request)

        generation = _allowed_generation
        # Off the event loop: these are blocking supabase-py calls.
        resolved_org = await asyncio.to_thread(_check_billing_gate, user_id, requested_org)
        _remember_allowed(cache_key, resolved_org, generation)
    except PlanRequiredError as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"error": "plan_required"}
        return JSONResponse(status_code=402, content=detail)
    except Exception:
        # Do not block requests when billing lookup fails unexpectedly.
        return await call_next(request)

    return await call_next(request)

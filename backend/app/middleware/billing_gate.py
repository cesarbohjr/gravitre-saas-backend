"""HTTP middleware: enforce trial/subscription gating on product API paths."""
from __future__ import annotations

import asyncio
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


# (user_id, requested_org) -> monotonic expiry for a recent "not blocked"
# decision. The gate runs on every product API call; before this it made ~4
# sequential Supabase reads per request on the event loop. Only "allowed" is
# cached, briefly, so a block (or an unblock after payment) is never stale for
# more than a few seconds in the costly direction.
_ALLOWED_TTL_S = 30.0
_ALLOWED_MAX_ENTRIES = 5000
_allowed_until: dict[tuple[str, str], float] = {}


def _remember_allowed(key: tuple[str, str]) -> None:
    if len(_allowed_until) >= _ALLOWED_MAX_ENTRIES:
        _allowed_until.clear()
    _allowed_until[key] = time.monotonic() + _ALLOWED_TTL_S


def _check_billing_gate(user_id: str, requested_org: str) -> None:
    """Sync Supabase lookups; raises PlanRequiredError when the org is blocked."""
    settings = get_settings()
    client = get_supabase_client(settings)
    member_org_ids = list_member_org_ids(client, user_id)
    org_id = requested_org if requested_org in member_org_ids else pick_default_org_id(member_org_ids)
    if not org_id:
        return
    assert_org_not_blocked(client, org_id)


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
        if _allowed_until.get(cache_key, 0.0) > time.monotonic():
            return await call_next(request)

        # Off the event loop: these are blocking supabase-py calls.
        await asyncio.to_thread(_check_billing_gate, user_id, requested_org)
        _remember_allowed(cache_key)
    except PlanRequiredError as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"error": "plan_required"}
        return JSONResponse(status_code=402, content=detail)
    except Exception:
        # Do not block requests when billing lookup fails unexpectedly.
        return await call_next(request)

    return await call_next(request)

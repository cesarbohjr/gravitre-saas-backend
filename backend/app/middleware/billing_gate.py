"""HTTP middleware: enforce trial/subscription gating on product API paths."""
from __future__ import annotations

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

        client = get_supabase_client(settings)
        requested_org = (request.headers.get("x-org-id") or request.query_params.get("org_id") or "").strip()
        member_org_ids = list_member_org_ids(client, user_id)
        org_id = requested_org if requested_org in member_org_ids else pick_default_org_id(member_org_ids)
        if not org_id:
            return await call_next(request)

        assert_org_not_blocked(client, org_id)
    except PlanRequiredError as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"error": "plan_required"}
        return JSONResponse(status_code=402, content=detail)
    except Exception:
        # Do not block requests when billing lookup fails unexpectedly.
        return await call_next(request)

    return await call_next(request)

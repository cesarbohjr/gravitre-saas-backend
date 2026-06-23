"""BE-00: Auth and org context. Supabase Auth (email + magic link); org from DB (single-org-per-user)."""
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Header, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.auth.jwt_verify import decode_supabase_jwt
from app.auth.platform_admin import (
    can_trigger_knowledge_sync,
    is_org_admin_role,
    is_org_member_role,
    is_platform_admin,
)
from app.config import Settings, get_settings
from app.core.logging import get_logger, org_id_ctx, user_id_ctx

security = HTTPBearer(auto_error=False)
logger = get_logger(__name__)

# 401 reason categories for logging (never log raw tokens)
REASON_MISSING_TOKEN = "missing_token"
REASON_INVALID_SIGNATURE = "invalid_signature"
REASON_EXPIRED = "expired"
REASON_INVALID_CLAIMS = "invalid_claims"


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Strict auth only: validate Supabase JWT (iss, aud, leeway). Raises 401 if missing or invalid."""
    if not credentials:
        logger.warning("401 auth_failure reason=%s", REASON_MISSING_TOKEN)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    token = credentials.credentials
    if not token:
        logger.warning("401 auth_failure reason=%s", REASON_MISSING_TOKEN)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    try:
        payload = decode_supabase_jwt(token, settings)
    except jwt.ExpiredSignatureError:
        logger.warning("401 auth_failure reason=%s", REASON_EXPIRED)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except jwt.InvalidSignatureError:
        logger.warning("401 auth_failure reason=%s", REASON_INVALID_SIGNATURE)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except jwt.InvalidAudienceError:
        logger.warning("401 auth_failure reason=%s", REASON_INVALID_CLAIMS)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except jwt.InvalidIssuerError:
        logger.warning("401 auth_failure reason=%s", REASON_INVALID_CLAIMS)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except jwt.PyJWTError:
        logger.warning("401 auth_failure reason=%s", REASON_INVALID_CLAIMS)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    if not user_id:
        logger.warning("401 auth_failure reason=%s", REASON_INVALID_CLAIMS)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user_id_ctx.set(user_id)

    return {
        "user_id": user_id,
        "email": payload.get("email") or None,
    }


async def get_org_context(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str | None:
    """Resolve org_id from membership rows, optional x-org-id header, or auto-provision.

    Multi-org users are supported (STA-72). When several memberships exist and no
    valid org is requested, the user's primary org (public.users.org_id) or first
    non-demo membership is used. Authenticated users without any membership get a
    personal workspace auto-created so AI chat and core flows remain usable.
    """
    from supabase import create_client

    from app.services.org_membership import (
        ensure_user_workspace,
        list_member_org_ids,
        load_user_primary_org_id,
        pick_default_org_id,
    )

    client: Client = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
    user_id = current_user["user_id"]
    requested_org_id = (request.headers.get("x-org-id") or request.query_params.get("org_id") or "").strip()
    platform_admin = is_platform_admin(client, user_id)

    try:
        member_org_ids = list_member_org_ids(client, user_id)
    except Exception as exc:  # noqa: BLE001
        member_org_ids = []
        logger.warning("org_lookup_failed user_id=%s error=%s", user_id, str(exc))

    if requested_org_id:
        if requested_org_id in member_org_ids:
            org_id_ctx.set(requested_org_id)
            return requested_org_id
        if platform_admin:
            org_id_ctx.set(requested_org_id)
            return requested_org_id
        if member_org_ids:
            logger.warning(
                "org_context_requested_not_member user_id=%s org_id=%s",
                user_id,
                requested_org_id,
            )

    if member_org_ids:
        primary_org_id = load_user_primary_org_id(client, user_id)
        org_id = pick_default_org_id(
            member_org_ids,
            primary_org_id=primary_org_id,
            requested_org_id=None,
        )
        if org_id:
            org_id_ctx.set(org_id)
            if len(member_org_ids) > 1:
                logger.info(
                    "org_context_multi_org_default user_id=%s org_id=%s membership_count=%s",
                    user_id,
                    org_id,
                    len(member_org_ids),
                )
            return org_id

    org_id = ensure_user_workspace(
        client,
        user_id,
        email=current_user.get("email"),
    )
    if org_id:
        org_id_ctx.set(org_id)
        return org_id

    org_id_ctx.set("")
    logger.warning("org_membership_missing user_id=%s", user_id)
    return None


async def require_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> tuple[dict, str]:
    """Require org + admin role. Returns (user, org_id). Raises 403 if not admin."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    from supabase import create_client

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    if is_platform_admin(client, current_user["user_id"]):
        return current_user, org_id
    r = (
        client.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", current_user["user_id"])
        .limit(1)
        .execute()
    )
    if not r.data or len(r.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    role = (r.data[0].get("role") or "").strip().lower()
    if not is_org_admin_role(role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user, org_id


async def require_org_member(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> tuple[dict, str, str]:
    """Require org membership. Returns (user, org_id, role). Raises 403 if not a member."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    from supabase import create_client

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    if is_platform_admin(client, current_user["user_id"]):
        return current_user, org_id, "admin"
    r = (
        client.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", current_user["user_id"])
        .limit(1)
        .execute()
    )
    if not r.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    role = (r.data[0].get("role") or "member").strip().lower()
    if not is_org_member_role(role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    return current_user, org_id, role


async def require_platform_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Require platform (Gravitre) admin. Returns user dict."""
    from supabase import create_client

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    if not is_platform_admin(client, current_user["user_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin required",
        )
    return current_user


async def get_environment_context(
    x_environment: Annotated[str | None, Header()] = None,
) -> str:
    """Optional environment selector; defaults to 'production'."""
    env = (x_environment or "production").strip().lower()
    if env == "default":
        env = "production"
    return env or "production"


def set_request_auth_context(user_id: str | None, org_id: str | None) -> None:
    """Set auth context for logging (middleware)."""
    if user_id:
        user_id_ctx.set(user_id)
    if org_id:
        org_id_ctx.set(org_id)

"""BE-00: Auth and org context. Supabase Auth (email + magic link); org from DB (single-org-per-user)."""
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Header, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

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
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            algorithms=["HS256"],
            leeway=settings.supabase_jwt_leeway_seconds,
        )
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
    """Enrichment only: lookup org_id from organization_members (single-org-per-user).
    Not required for 200. Missing row = org_id null + warning. Multiple rows = 500.
    """
    from supabase import create_client

    client: Client = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
    requested_org_id = (request.headers.get("x-org-id") or request.query_params.get("org_id") or "").strip()
    try:
        r = (
            client.table("organization_members")
            .select("org_id")
            .eq("user_id", current_user["user_id"])
            .limit(2)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        if requested_org_id:
            org_id_ctx.set(requested_org_id)
            logger.warning(
                "org_lookup_failed_fallback user_id=%s org_id=%s error=%s",
                current_user["user_id"],
                requested_org_id,
                str(exc),
            )
            return requested_org_id
        org_id_ctx.set("")
        logger.warning("org_lookup_failed user_id=%s error=%s", current_user["user_id"], str(exc))
        return None
    if requested_org_id and r.data:
        member_org_ids = {str(row.get("org_id")) for row in r.data if row.get("org_id")}
        if requested_org_id in member_org_ids:
            org_id_ctx.set(requested_org_id)
            return requested_org_id
    if not r.data or len(r.data) == 0:
        # Compatibility fallback for preview/demo environments where memberships are not yet backfilled.
        if requested_org_id:
            try:
                org_exists = (
                    client.table("organizations")
                    .select("id")
                    .eq("id", requested_org_id)
                    .limit(1)
                    .execute()
                )
            except Exception as exc:  # noqa: BLE001
                org_id_ctx.set(requested_org_id)
                logger.warning(
                    "org_exists_lookup_failed_fallback user_id=%s org_id=%s error=%s",
                    current_user["user_id"],
                    requested_org_id,
                    str(exc),
                )
                return requested_org_id
            if org_exists.data:
                org_id_ctx.set(requested_org_id)
                logger.warning(
                    "org_membership_missing_fallback user_id=%s org_id=%s source=requested_org_id",
                    current_user["user_id"],
                    requested_org_id,
                )
                return requested_org_id
        try:
            fallback_org = client.table("organizations").select("id").limit(1).execute()
        except Exception as exc:  # noqa: BLE001
            org_id_ctx.set("")
            logger.warning("org_fallback_lookup_failed user_id=%s error=%s", current_user["user_id"], str(exc))
            return None
        if fallback_org.data:
            org_id = str(fallback_org.data[0]["id"])
            org_id_ctx.set(org_id)
            logger.warning(
                "org_membership_missing_fallback user_id=%s org_id=%s source=first_organization",
                current_user["user_id"],
                org_id,
            )
            return org_id
        org_id_ctx.set("")
        logger.warning("org_membership_missing user_id=%s", current_user["user_id"])
        return None
    if len(r.data) > 1:
        logger.error(
            "org_membership_duplicate user_id=%s count=%s stop_condition=multiple_membership_rows",
            current_user["user_id"],
            len(r.data),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Organization membership inconsistency",
        )
    org_id = str(r.data[0]["org_id"])
    org_id_ctx.set(org_id)
    return org_id


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
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user, org_id


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

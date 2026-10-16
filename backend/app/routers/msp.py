"""Release 4 — MSP multi-tenant management endpoints.

Endpoints:
    GET  /api/msp/client-orgs          List child orgs visible to the caller.
    POST /api/msp/switch-client        Issue a short-lived scoped token for a child org.
    GET  /api/msp/client-orgs/{org_id} Single child-org details + membership count.

Access model:
    The caller must be an admin or owner of at least one MSP parent org
    (``parent_org_id`` set on the child org). Platform admins can access any org
    regardless. A user who is only a direct member of a child org cannot use these
    endpoints — this is an MSP-admin-only surface.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user
from app.auth.platform_admin import ORG_ADMIN_ROLES, is_platform_admin
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger
from app.services.msp_org_context import (
    list_child_orgs_for_msp_admin,
    parent_org_id_for,
    _user_role_in_org,
)
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/msp", tags=["msp"])
logger = get_logger(__name__)

AUDIT_MSP_CLIENT_LISTED = "msp.client.listed"
AUDIT_MSP_CLIENT_SWITCHED = "msp.client.switched"
AUDIT_MSP_CLIENT_VIEWED = "msp.client.viewed"

# Scoped MSP token TTL — short-lived by design; caller should request fresh tokens.
_MSP_TOKEN_TTL_MINUTES = 60


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_msp_enabled(settings: Settings) -> None:
    if not getattr(settings, "msp_parent_org_enabled", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MSP parent-org delegation is not enabled for this deployment.",
        )


def _admin_parent_org_ids(
    client,
    user_id: str,
    is_platform: bool,
) -> list[str]:
    """Return org IDs where the user has admin/owner role.

    For platform admins, returns all orgs (expensive — platform-admin path only).
    For regular users, queries organization_members filtered to admin/owner roles.
    """
    if is_platform:
        # Platform admin can manage all orgs — return all parent-capable orgs.
        # Practical limit: orgs with children only; client callers filter afterwards.
        try:
            resp = (
                client.table("organizations")
                .select("id")
                .is_("parent_org_id", "null")
                .limit(500)
                .execute()
            )
            return [str(r["id"]) for r in (resp.data or []) if r.get("id")]
        except Exception as exc:  # noqa: BLE001
            logger.warning("msp_platform_admin_orgs_failed user_id=%s error=%s", user_id, exc)
            return []

    try:
        resp = (
            client.table("organization_members")
            .select("org_id, role")
            .eq("user_id", user_id)
            .in_("role", list(ORG_ADMIN_ROLES))
            .limit(100)
            .execute()
        )
        return [str(r["org_id"]) for r in (resp.data or []) if r.get("org_id")]
    except Exception as exc:  # noqa: BLE001
        logger.warning("msp_admin_orgs_failed user_id=%s error=%s", user_id, exc)
        return []


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ClientOrgSummary(BaseModel):
    id: str
    name: str | None
    slug: str | None
    parent_org_id: str
    created_at: str | None


class ListClientOrgsResponse(BaseModel):
    client_orgs: list[ClientOrgSummary]
    total: int


class SwitchClientRequest(BaseModel):
    client_org_id: str = Field(..., min_length=1, description="Child org UUID to switch context to")


class SwitchClientResponse(BaseModel):
    token: str = Field(..., description="Short-lived JWT scoped to the child org")
    client_org_id: str
    expires_at: str


class ClientOrgDetailResponse(BaseModel):
    id: str
    name: str | None
    slug: str | None
    parent_org_id: str
    created_at: str | None
    member_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/client-orgs", response_model=ListClientOrgsResponse)
def list_client_orgs(
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ListClientOrgsResponse:
    """List all child (client) orgs the caller has MSP admin access to.

    The caller must be an admin/owner of at least one parent org, or a platform
    admin. Returns all child orgs across all parent orgs the user manages.
    """
    _require_msp_enabled(settings)
    user_id = current_user["user_id"]
    client = shared_service_client(settings, create_client)

    platform_admin = is_platform_admin(client, user_id)
    parent_org_ids = _admin_parent_org_ids(client, user_id, is_platform=platform_admin)

    if not parent_org_ids:
        write_audit_event(
            client,
            event_type=AUDIT_MSP_CLIENT_LISTED,
            org_id=None,
            user_id=user_id,
            metadata={"parent_count": 0, "client_count": 0},
        )
        return ListClientOrgsResponse(client_orgs=[], total=0)

    # Collect children across all admin parent orgs.
    all_children: list[ClientOrgSummary] = []
    for parent_id in parent_org_ids:
        children = list_child_orgs_for_msp_admin(client, user_id, parent_id)
        for child in children:
            all_children.append(
                ClientOrgSummary(
                    id=child["id"],
                    name=child.get("name"),
                    slug=child.get("slug"),
                    parent_org_id=parent_id,
                    created_at=str(child["created_at"]) if child.get("created_at") else None,
                )
            )

    write_audit_event(
        client,
        event_type=AUDIT_MSP_CLIENT_LISTED,
        org_id=None,
        user_id=user_id,
        metadata={"parent_count": len(parent_org_ids), "client_count": len(all_children)},
    )
    return ListClientOrgsResponse(client_orgs=all_children, total=len(all_children))


@router.post("/switch-client", response_model=SwitchClientResponse)
def switch_client(
    body: SwitchClientRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SwitchClientResponse:
    """Issue a short-lived JWT scoped to the given child org.

    Validates:
    1. MSP feature flag is on.
    2. caller is admin/owner of the child org's parent, OR a platform admin.
    3. The requested org actually has a parent_org_id (is a managed client).

    The returned token embeds ``org_id=<child_org_id>`` so subsequent API calls
    authenticated with it will resolve to the child org context (same as the
    existing /api/organizations/{id}/switch flow for direct members).
    """
    _require_msp_enabled(settings)
    user_id = current_user["user_id"]
    client_org_id = str(body.client_org_id).strip()

    client = shared_service_client(settings, create_client)
    platform_admin = is_platform_admin(client, user_id)

    # Verify the requested org is actually a managed child org.
    parent_id = parent_org_id_for(client, client_org_id)
    if not parent_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested org is not a managed client org (no parent_org_id set).",
        )

    # Check delegation authority.
    if not platform_admin:
        role = _user_role_in_org(client, user_id, parent_id)
        if role not in ORG_ADMIN_ROLES:
            logger.warning(
                "msp_switch_client_denied user_id=%s client_org_id=%s parent_org_id=%s caller_role=%s",
                user_id,
                client_org_id,
                parent_id,
                role,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be an admin or owner of the parent org to switch to this client.",
            )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=_MSP_TOKEN_TTL_MINUTES)
    token = jwt.encode(
        {
            "sub": user_id,
            "email": current_user.get("email"),
            "aud": settings.jwt_audience,
            "iss": settings.jwt_issuer,
            "org_id": client_org_id,
            "msp_parent_org_id": parent_id,
            "msp_delegated": True,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )

    write_audit_event(
        client,
        event_type=AUDIT_MSP_CLIENT_SWITCHED,
        org_id=client_org_id,
        user_id=user_id,
        metadata={
            "parent_org_id": parent_id,
            "client_org_id": client_org_id,
            "expires_at": expires_at.isoformat(),
        },
    )
    logger.info(
        "msp_client_switched user_id=%s parent_org_id=%s client_org_id=%s",
        user_id,
        parent_id,
        client_org_id,
    )
    return SwitchClientResponse(
        token=token,
        client_org_id=client_org_id,
        expires_at=expires_at.isoformat(),
    )


@router.get("/client-orgs/{org_id}", response_model=ClientOrgDetailResponse)
def get_client_org(
    org_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ClientOrgDetailResponse:
    """Retrieve details for a single client org, including its member count.

    Caller must be admin/owner of the child's parent org, or a platform admin.
    """
    _require_msp_enabled(settings)
    user_id = current_user["user_id"]
    org_id_str = str(org_id)
    client = shared_service_client(settings, create_client)

    platform_admin = is_platform_admin(client, user_id)
    parent_id = parent_org_id_for(client, org_id_str)
    if not parent_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Org not found or is not a managed client org.",
        )

    if not platform_admin:
        role = _user_role_in_org(client, user_id, parent_id)
        if role not in ORG_ADMIN_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you must be an admin/owner of the parent org.",
            )

    try:
        org_resp = (
            client.table("organizations")
            .select("id, name, slug, parent_org_id, created_at")
            .eq("id", org_id_str)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("msp_get_client_org_failed org_id=%s error=%s", org_id_str, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Database error.")

    if not org_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client org not found.")

    org = org_resp.data[0]

    # Member count (best-effort — zero on failure).
    member_count = 0
    try:
        mc_resp = (
            client.table("organization_members")
            .select("id", count="exact")
            .eq("org_id", org_id_str)
            .execute()
        )
        member_count = mc_resp.count or 0
    except Exception:  # noqa: BLE001
        pass

    write_audit_event(
        client,
        event_type=AUDIT_MSP_CLIENT_VIEWED,
        org_id=org_id_str,
        user_id=user_id,
        metadata={"parent_org_id": parent_id},
    )
    return ClientOrgDetailResponse(
        id=str(org.get("id")),
        name=org.get("name"),
        slug=org.get("slug"),
        parent_org_id=str(org.get("parent_org_id")),
        created_at=str(org.get("created_at")) if org.get("created_at") else None,
        member_count=member_count,
    )

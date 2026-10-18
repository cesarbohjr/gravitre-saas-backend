"""Customer-owner-managed MSP delegation APIs. No cross-tenant read access."""
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.dependencies import get_current_user
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from supabase import create_client
from app.services.msp_delegation_policy import AccessTier, ALL_ACTIONS
from app.services.msp_delegation_preflight import _member_role
from app.services.msp_org_context import parent_org_id_for

router = APIRouter(prefix="/api/msp/delegations", tags=["msp"])


class GrantRequest(BaseModel):
    provider_org_id: UUID
    customer_org_id: UUID
    grantee_user_id: UUID
    tier: AccessTier
    actions: list[str] = Field(min_length=1, max_length=12)
    expires_at: datetime


def _customer_owner(client, user_id: str, customer_id: str) -> None:
    if _member_role(client, org_id=customer_id, user_id=user_id) != "owner":
        raise HTTPException(403, "Customer owner required")


@router.post("", status_code=201)
def grant_access(
    body: GrantRequest,
    user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    # Service-key DB access is used ONLY after verified customer ownership.
    client = shared_service_client(settings, create_client)
    provider, customer, grantee = map(str, (body.provider_org_id, body.customer_org_id, body.grantee_user_id))
    _customer_owner(client, user["user_id"], customer)
    if provider == customer or parent_org_id_for(client, customer) != provider:
        raise HTTPException(403, "Unlinked customer")
    if _member_role(client, org_id=provider, user_id=grantee) not in {"owner", "admin", "member"}:
        raise HTTPException(403, "Grantee is not a provider member")
    if body.expires_at.tzinfo is None or body.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(422, "Future timezone-aware expiration required")
    from app.services.msp_delegation_policy import OVERVIEW_ACTIONS, ADMIN_ACTIONS, SENSITIVE_ACTIONS
    allowed = set(OVERVIEW_ACTIONS)
    if body.tier >= AccessTier.ADMINISTRATION:
        allowed.update(ADMIN_ACTIONS)
    if body.tier >= AccessTier.SENSITIVE:
        allowed.update(SENSITIVE_ACTIONS)
    if not set(body.actions).issubset(allowed & ALL_ACTIONS):
        raise HTTPException(422, "Actions exceed selected tier")
    row = client.table("msp_delegations").insert({
        "provider_org_id": provider, "customer_org_id": customer,
        "grantee_user_id": grantee, "tier": int(body.tier),
        "actions": sorted(set(body.actions)),
        "approved_by_customer_user_id": user["user_id"],
        "expires_at": body.expires_at.isoformat(),
    }).execute()
    if not row.data:
        raise HTTPException(503, "Grant not persisted")
    grant_id = str(row.data[0]["id"])
    return {"id": grant_id, "status": "stored_not_activated"}


@router.post("/{delegation_id}/revoke")
def revoke_access(
    delegation_id: UUID,
    customer_org_id: UUID,
    user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    client = shared_service_client(settings, create_client)
    customer = str(customer_org_id)
    _customer_owner(client, user["user_id"], customer)
    rows = client.table("msp_delegations").select("id,provider_org_id,customer_org_id,revoked_at").eq(
        "id", str(delegation_id)).eq("customer_org_id", customer).limit(1).execute().data or []
    if not rows:
        raise HTTPException(404, "Delegation not found")
    row = rows[0]
    if row.get("revoked_at"):
        return {"id": str(delegation_id), "revoked": True}
    result = client.rpc("msp_revoke_delegation_atomic", {
        "p_delegation_id": str(delegation_id),
        "p_customer_org_id": customer,
        "p_actor_user_id": user["user_id"],
    }).execute()
    if result.data is not True:
        raise HTTPException(409, "Delegation changed; retry")
    return {"id": str(delegation_id), "revoked": True}


@router.get("/customer/{customer_org_id}/health")
def delegated_customer_health(
    customer_org_id: UUID,
    provider_org_id: UUID,
    user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Allowlisted OVERVIEW action only. No generic tenant read or org switching.

    Deliberately returns a minimal customer organization health projection;
    conversations, billing details and all other resources remain inaccessible.
    """
    from app.services.msp_delegated_access import authorize_live_action
    if not settings.msp_parent_org_enabled:
        raise HTTPException(403, "MSP delegation not enabled")
    client = shared_service_client(settings, create_client)
    customer, provider = str(customer_org_id), str(provider_org_id)
    if not authorize_live_action(
        client, provider_org_id=provider, customer_org_id=customer,
        grantee_user_id=user["user_id"], action="account.health.read",
    ):
        raise HTTPException(403, "Delegation denied")
    # Explicitly scope the only service-role read to the already-authorized customer.
    response = (
        client.table("organizations")
        .select("id,status")
        .eq("id", customer)
        .limit(1).execute()
    )
    if not response.data:
        raise HTTPException(404, "Customer not found")
    row = response.data[0]
    if str(row.get("id")) != customer:
        raise HTTPException(403, "Customer scope mismatch")
    return {"customer_org_id": customer, "status": row.get("status")}

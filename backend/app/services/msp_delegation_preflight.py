"""Server-side MSP delegation preflight.

Never accepts caller-supplied booleans as authorization evidence. Only checks
explicit customer approval, provider membership and current parent linkage.
This preflight does not bypass require_org_member or Supabase RLS, and must
not be used to switch into a customer organization.
"""
from __future__ import annotations

from typing import Any

from app.services.msp_delegation_policy import Delegation, is_allowed
from app.services.msp_org_context import parent_org_id_for


def _member_role(client: Any, *, org_id: str, user_id: str) -> str | None:
    try:
        rows = (
            client.table("organization_members")
            .select("role")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data or []
        )
        return str(rows[0].get("role") or "").strip().lower() if rows else None
    except Exception:  # Fail closed on errors or schema drift.
        return None


def delegation_preflight(
    client: Any,
    grant: Delegation | None,
    *,
    provider_org_id: str,
    customer_org_id: str,
    user_id: str,
    action: str,
) -> bool:
    """Check a server-loaded delegation against live memberships and link.

    Customer approver must remain an owner/admin of the customer organization.
    Grantee must remain a member of provider. Grants do not grant customer
    data visibility: customer-scoped APIs and RLS must still authorize access.
    """
    if grant is None:
        return False
    provider_role = _member_role(client, org_id=provider_org_id, user_id=user_id)
    approver_role = _member_role(
        client, org_id=customer_org_id, user_id=grant.approved_by_customer_user_id
    )
    # Only the direct customer owner is allowed to approve sensitive delegation.
    if approver_role != "owner":
        return False
    if provider_role not in {"owner", "admin", "member"}:
        return False
    if parent_org_id_for(client, customer_org_id) != provider_org_id:
        return False
    return is_allowed(
        grant,
        provider_org_id=provider_org_id,
        customer_org_id=customer_org_id,
        user_id=user_id,
        action=action,
        customer_approval_verified=True,
        provider_membership_verified=True,
        customer_relationship_verified=True,
    )

"""Fail-closed, uncached action-scoped MSP authorization for allowlisted endpoints.

This is *not* an org-switch mechanism. Each invocation checks a live persisted
grant, customer owner, provider member, relationship, tier and action. Never
authorize generic service-role customer queries from this helper.
"""
from datetime import datetime, timezone
from typing import Any

from app.services.msp_delegation_policy import AccessTier, Delegation
from app.services.msp_delegation_preflight import delegation_preflight


def authorize_live_action(
    client: Any, *, provider_org_id: str, customer_org_id: str,
    grantee_user_id: str, action: str,
) -> bool:
    """Read fresh grants for each request, including after revoke or expiry.

    Any storage failure, malformed grant, or missing membership fails closed.
    """
    try:
        response = (
            client.table("msp_delegations")
            .select("provider_org_id,customer_org_id,grantee_user_id,tier,actions,"
                    "approved_by_customer_user_id,expires_at,revoked_at")
            .eq("provider_org_id", provider_org_id)
            .eq("customer_org_id", customer_org_id)
            .eq("grantee_user_id", grantee_user_id)
            .is_("revoked_at", "null")
            .gt("expires_at", datetime.now(timezone.utc).isoformat())
            .execute()
        )
        # Bound query work; multiple grants are checked independently.
        for row in (response.data or []):
            try:
                grant = Delegation(
                    provider_org_id=str(row["provider_org_id"]),
                    customer_org_id=str(row["customer_org_id"]),
                    grantee_user_id=str(row["grantee_user_id"]),
                    tier=AccessTier(int(row["tier"])),
                    actions=frozenset(row["actions"]),
                    approved_by_customer_user_id=str(row["approved_by_customer_user_id"]),
                    expires_at=datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")),
                    revoked_at=(
                        datetime.fromisoformat(row["revoked_at"].replace("Z", "+00:00"))
                        if row.get("revoked_at") else None
                    ),
                )
                if delegation_preflight(
                    client, grant, provider_org_id=provider_org_id,
                    customer_org_id=customer_org_id,
                    user_id=grantee_user_id, action=action,
                ):
                    return True
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
    except Exception:
        return False
    return False

"""Fail-closed MSP delegated-access policy foundation.

A delegation is an additional permission constraint, never a replacement for
organization membership, customer consent, API authorization, or database RLS.
Parent/child organization links do not grant data access.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum


class AccessTier(IntEnum):
    OVERVIEW = 1
    ADMINISTRATION = 2
    SENSITIVE = 3


OVERVIEW_ACTIONS = frozenset({"account.health.read", "usage.aggregate.read", "billing.summary.read"})
ADMIN_ACTIONS = frozenset({"agent.configure", "workflow.manage", "connector.configure"})
SENSITIVE_ACTIONS = frozenset({"conversation.read", "document.read", "memory.read"})
ALL_ACTIONS = OVERVIEW_ACTIONS | ADMIN_ACTIONS | SENSITIVE_ACTIONS


@dataclass(frozen=True)
class Delegation:
    provider_org_id: str
    customer_org_id: str
    grantee_user_id: str
    tier: AccessTier
    actions: frozenset[str]
    approved_by_customer_user_id: str
    expires_at: datetime
    revoked_at: datetime | None = None


def is_allowed(
    grant: Delegation | None,
    *,
    provider_org_id: str,
    customer_org_id: str,
    user_id: str,
    action: str,
    now: datetime | None = None,
) -> bool:
    """Check scope and expiry; callers MUST also independently enforce RLS.

    This function never authorizes a database query by itself.
    """
    if grant is None or action not in ALL_ACTIONS:
        return False
    if not all((provider_org_id, customer_org_id, user_id, grant.approved_by_customer_user_id)):
        return False
    if provider_org_id == customer_org_id:
        return False
    if (grant.provider_org_id, grant.customer_org_id, grant.grantee_user_id) != (
        provider_org_id, customer_org_id, user_id
    ):
        return False
    if grant.revoked_at is not None or action not in grant.actions:
        return False
    allowed_for_tier = set(OVERVIEW_ACTIONS)
    if grant.tier >= AccessTier.ADMINISTRATION:
        allowed_for_tier.update(ADMIN_ACTIONS)
    if grant.tier >= AccessTier.SENSITIVE:
        allowed_for_tier.update(SENSITIVE_ACTIONS)
    if action not in allowed_for_tier:
        return False
    if grant.expires_at.tzinfo is None:
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return False
    return current < grant.expires_at

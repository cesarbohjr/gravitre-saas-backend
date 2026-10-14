"""MSP parent-org access (Release 4 Option A scaffold).

Parent links describe the organizational hierarchy; they do not delegate access.
Until explicit client-scoped delegation ships, the user's existing child-org
membership remains the authority in both application checks and database RLS.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def _missing_parent_column(exc: Exception) -> bool:
    text = str(exc)
    return "parent_org_id" in text and ("42703" in text or "does not exist" in text.lower())


def parent_org_id_for(client: Any, org_id: str) -> str | None:
    try:
        row = (
            client.table("organizations")
            .select("parent_org_id")
            .eq("id", org_id)
            .limit(1)
            .execute()
        )
        if not row.data:
            return None
        parent = row.data[0].get("parent_org_id")
        return str(parent) if parent else None
    except Exception as exc:  # noqa: BLE001
        if _missing_parent_column(exc):
            return None
        logger.warning("msp_parent_org_lookup_failed org_id=%s error=%s", org_id, exc)
        return None


def msp_parent_grants_access(
    client: Any,
    *,
    user_id: str,
    requested_org_id: str,
    member_org_ids: list[str],
) -> bool:
    """Recognize a parent relationship only with explicit child membership.

    A parent member (including an admin) cannot inherit all customer data or
    write permissions merely because an organization has a parent link.
    """
    if requested_org_id not in member_org_ids:
        return False
    parent = parent_org_id_for(client, requested_org_id)
    if not parent:
        return False
    if parent not in member_org_ids:
        return False
    logger.info(
        "msp_parent_org_access user_id=%s parent_org_id=%s client_org_id=%s",
        user_id,
        parent,
        requested_org_id,
    )
    return True

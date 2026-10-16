"""MSP parent-org access — Release 4 real implementation.

Delegation model (Option A — role-gated parent trust):
    A user is granted access to a child org if ALL of the following hold:
    1. The child org has `parent_org_id` pointing to a parent org.
    2. The requesting user is a member of that parent org with role admin or owner.
    3. The child org's `parent_org_id` is not NULL (explicit, not implied).

This replaces the earlier stub which required the user to already be a direct
member of the child org (making the function a no-op). The real check delegates
access transitively: parent admin → child org, without adding the user as a
direct member of the child. Supabase RLS is enforced at the DB level for all
queries that run in the child-org context; this layer only governs whether the
application resolves org_id to the child.

Audit: every successful delegation event is logged at INFO with a structured key
``msp_delegation_granted`` so log aggregators can alert on unusual cross-org access.
"""
from __future__ import annotations

from typing import Any

from app.auth.platform_admin import ORG_ADMIN_ROLES
from app.core.logging import get_logger

logger = get_logger(__name__)


def _missing_parent_column(exc: Exception) -> bool:
    text = str(exc)
    return "parent_org_id" in text and ("42703" in text or "does not exist" in text.lower())


def parent_org_id_for(client: Any, org_id: str) -> str | None:
    """Return the parent_org_id for the given child org, or None."""
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


def _user_role_in_org(client: Any, user_id: str, org_id: str) -> str | None:
    """Return the user's role in the given org, or None if not a member."""
    try:
        resp = (
            client.table("organization_members")
            .select("role")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        return str(resp.data[0].get("role") or "").strip().lower() or None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "msp_role_lookup_failed user_id=%s org_id=%s error=%s",
            user_id,
            org_id,
            exc,
        )
        return None


def msp_parent_grants_access(
    client: Any,
    *,
    user_id: str,
    requested_org_id: str,
    member_org_ids: list[str],
) -> bool:
    """Return True when the user's parent-org admin role grants access to a child org.

    The caller (auth/dependencies.py) has already confirmed the user is NOT a
    direct member of ``requested_org_id``. This function checks whether the user
    is an admin/owner of the org's parent, which grants transitive read access
    to the child without adding a direct membership row.

    Short-circuit order (fail fast, fewest DB calls):
    1. If the user has no memberships at all → False (one set check, zero DB calls).
    2. Look up parent_org_id for requested_org_id (1 DB call).
    3. Check parent is in member_org_ids (set check, zero DB calls).
    4. Verify the user's role in parent is admin or owner (1 DB call only if above pass).
    """
    # No memberships at all — skip DB entirely.
    if not member_org_ids:
        return False

    # Fetch the child org's declared parent (1 query).
    parent_org_id = parent_org_id_for(client, requested_org_id)
    if not parent_org_id:
        return False

    # User must be a member of the parent at all (set check, O(1)).
    if parent_org_id not in member_org_ids:
        return False

    # User must be admin or owner in the parent (1 query).
    role = _user_role_in_org(client, user_id, parent_org_id)
    if role not in ORG_ADMIN_ROLES:
        return False

    logger.info(
        "msp_delegation_granted user_id=%s parent_org_id=%s client_org_id=%s parent_role=%s",
        user_id,
        parent_org_id,
        requested_org_id,
        role,
    )
    return True


def list_child_orgs_for_msp_admin(
    client: Any,
    user_id: str,
    parent_org_id: str,
) -> list[dict[str, Any]]:
    """Return all child orgs (id, name, slug, created_at) under a given parent org.

    The caller must verify the user has admin/owner role in parent_org_id before
    calling this. Returns [] on any DB error (never raises).
    """
    try:
        resp = (
            client.table("organizations")
            .select("id, name, slug, created_at")
            .eq("parent_org_id", parent_org_id)
            .order("created_at")
            .limit(200)
            .execute()
        )
        return [
            {
                "id": str(row.get("id")),
                "name": row.get("name"),
                "slug": row.get("slug"),
                "created_at": row.get("created_at"),
            }
            for row in (resp.data or [])
            if row.get("id")
        ]
    except Exception as exc:  # noqa: BLE001
        if _missing_parent_column(exc):
            return []
        logger.warning(
            "list_child_orgs_failed user_id=%s parent_org_id=%s error=%s",
            user_id,
            parent_org_id,
            exc,
        )
        return []

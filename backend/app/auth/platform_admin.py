"""Platform (master) admin registry — service-role only, no broad RLS weakening."""
from __future__ import annotations

import re
from typing import Any

ORG_ADMIN_ROLES = frozenset({"admin", "owner"})
ORG_MEMBER_ROLES = frozenset({"admin", "owner", "member", "viewer"})
ORG_KNOWLEDGE_SYNC_ROLES = frozenset({"admin", "owner", "member"})


def is_org_admin_role(role: str | None) -> bool:
    return (role or "").strip().lower() in ORG_ADMIN_ROLES


# Custom roles a workspace defines in Trust & Safety > Role permissions use keys like
# "support_lead"; a membership on one is still a membership.
_CUSTOM_ROLE_KEY = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


def is_org_member_role(role: str | None) -> bool:
    normalized = (role or "").strip().lower()
    return normalized in ORG_MEMBER_ROLES or bool(_CUSTOM_ROLE_KEY.match(normalized))


def can_trigger_knowledge_sync(role: str | None) -> bool:
    return (role or "").strip().lower() in ORG_KNOWLEDGE_SYNC_ROLES


def is_platform_admin(client: Any, user_id: str) -> bool:
    if not user_id:
        return False
    try:
        response = (
            client.table("platform_admins")
            .select("user_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return bool(response.data)
    except Exception:
        return False


def is_platform_admin_email(client: Any, email: str | None) -> bool:
    normalized = (email or "").strip().lower()
    if not normalized:
        return False
    try:
        response = (
            client.table("platform_admins")
            .select("email")
            .eq("email", normalized)
            .limit(1)
            .execute()
        )
        return bool(response.data)
    except Exception:
        return False

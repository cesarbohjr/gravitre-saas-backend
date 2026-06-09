"""Platform (master) admin registry — service-role only, no broad RLS weakening."""
from __future__ import annotations

from typing import Any

MASTER_ADMIN_EMAIL = "cesar.bohorquez.jr@gmail.com"

ORG_ADMIN_ROLES = frozenset({"admin", "owner"})


def is_org_admin_role(role: str | None) -> bool:
    return (role or "").strip().lower() in ORG_ADMIN_ROLES


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
    except Exception:
        return False
    if response.error:
        return False
    return bool(response.data)


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
    except Exception:
        return normalized == MASTER_ADMIN_EMAIL.lower()
    if response.error:
        return normalized == MASTER_ADMIN_EMAIL.lower()
    return bool(response.data)

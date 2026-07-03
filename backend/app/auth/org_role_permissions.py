"""Authoritative org role capability matrix for Settings → Permissions."""
from __future__ import annotations

from typing import Any

ORG_ROLES: tuple[str, ...] = ("admin", "member", "viewer")

ORG_ROLE_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "key": "view_intelligence",
        "capability": "View dashboards & intelligence",
        "access": {"admin": True, "member": True, "viewer": True},
    },
    {
        "key": "run_ai_chat",
        "capability": "Run Gravitre AI & chat",
        "access": {"admin": True, "member": True, "viewer": True},
    },
    {
        "key": "create_agents_workflows",
        "capability": "Create agents & workflows",
        "access": {"admin": True, "member": True, "viewer": False},
    },
    {
        "key": "install_marketplace",
        "capability": "Install marketplace packs",
        "access": {"admin": True, "member": False, "viewer": False},
    },
    {
        "key": "manage_connectors",
        "capability": "Manage connectors",
        "access": {"admin": True, "member": True, "viewer": False},
    },
    {
        "key": "approve_writes",
        "capability": "Approve write actions",
        "access": {"admin": True, "member": True, "viewer": False},
    },
    {
        "key": "org_settings_billing",
        "capability": "Org settings & billing",
        "access": {"admin": True, "member": False, "viewer": False},
    },
    {
        "key": "team_roles",
        "capability": "Team invites & roles",
        "access": {"admin": True, "member": False, "viewer": False},
    },
    {
        "key": "audit_export",
        "capability": "Audit log export",
        "access": {"admin": True, "member": False, "viewer": False},
    },
)


def get_org_role_permissions_matrix() -> dict[str, Any]:
    return {
        "roles": list(ORG_ROLES),
        "capabilities": [
            {
                "key": row["key"],
                "capability": row["capability"],
                "access": {role: bool(row["access"].get(role, False)) for role in ORG_ROLES},
            }
            for row in ORG_ROLE_CAPABILITIES
        ],
    }

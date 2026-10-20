"""Authoritative org role capability matrix for Settings → Permissions."""
from __future__ import annotations

from typing import Any

ORG_ROLES: tuple[str, ...] = ("admin", "member", "viewer")

# One line per role for the role cards. Owners hold every admin capability.
ORG_ROLE_DESCRIPTIONS: dict[str, str] = {
    "admin": "Full control of the workspace, people and billing.",
    "member": "Builds and runs agents, approves day to day work.",
    "viewer": "Sees dashboards and asks Gravitre questions.",
}

ORG_ROLE_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "key": "view_intelligence",
        "capability": "View dashboards and intelligence",
        "area": "Insights",
        "access": {"admin": True, "member": True, "viewer": True},
    },
    {
        "key": "run_ai_chat",
        "capability": "Run Gravitre AI and chat",
        "area": "Insights",
        "access": {"admin": True, "member": True, "viewer": True},
    },
    {
        "key": "create_agents_workflows",
        "capability": "Create agents and workflows",
        "area": "Build",
        "access": {"admin": True, "member": True, "viewer": False},
    },
    {
        "key": "install_marketplace",
        "capability": "Install marketplace packs",
        "area": "Build",
        "access": {"admin": True, "member": False, "viewer": False},
    },
    {
        "key": "manage_connectors",
        "capability": "Manage connectors",
        "area": "Build",
        "access": {"admin": True, "member": True, "viewer": False},
    },
    {
        "key": "approve_writes",
        "capability": "Approve write actions",
        "area": "Govern",
        "access": {"admin": True, "member": True, "viewer": False},
    },
    {
        "key": "org_settings_billing",
        "capability": "Org settings and billing",
        "area": "Govern",
        "access": {"admin": True, "member": False, "viewer": False},
    },
    {
        "key": "team_roles",
        "capability": "Invite and manage members",
        "area": "Govern",
        "access": {"admin": True, "member": False, "viewer": False},
    },
    {
        "key": "audit_export",
        "capability": "Export the audit trail",
        "area": "Govern",
        "access": {"admin": True, "member": False, "viewer": False},
    },
)


def get_org_role_permissions_matrix() -> dict[str, Any]:
    return {
        "roles": list(ORG_ROLES),
        "role_descriptions": {role: ORG_ROLE_DESCRIPTIONS.get(role, "") for role in ORG_ROLES},
        "capabilities": [
            {
                "key": row["key"],
                "capability": row["capability"],
                "area": row.get("area"),
                "access": {role: bool(row["access"].get(role, False)) for role in ORG_ROLES},
            }
            for row in ORG_ROLE_CAPABILITIES
        ],
    }

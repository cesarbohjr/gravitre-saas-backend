"""Authoritative org role capability matrix for Settings → Permissions."""
from __future__ import annotations

import re
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


CAPABILITY_KEYS: tuple[str, ...] = tuple(row["key"] for row in ORG_ROLE_CAPABILITIES)

# Where a workspace's edits live: organizations.settings["role_permissions"].
ROLE_PERMISSIONS_SETTINGS_KEY = "role_permissions"
# Admin always holds every capability so a workspace can't lock itself out.
LOCKED_ROLES: frozenset[str] = frozenset({"admin"})
MAX_ROLES = 20
MAX_NAME_LEN = 40
MAX_DESCRIPTION_LEN = 160
_ROLE_KEY = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


class RolePermissionsError(ValueError):
    """A role permissions update that can't be saved, with a message for the user."""


def _default_roles() -> list[dict[str, Any]]:
    return [
        {
            "key": role,
            "name": role.capitalize(),
            "description": ORG_ROLE_DESCRIPTIONS.get(role, ""),
            "capabilities": [row["key"] for row in ORG_ROLE_CAPABILITIES if row["access"].get(role)],
            "custom": False,
        }
        for role in ORG_ROLES
    ]


def stored_role_definitions(org_settings: Any) -> list[dict[str, Any]]:
    """The workspace's roles: the defaults, with any saved edits and custom roles applied."""
    stored = org_settings.get(ROLE_PERMISSIONS_SETTINGS_KEY) if isinstance(org_settings, dict) else None
    saved = stored.get("roles") if isinstance(stored, dict) else None
    if not isinstance(saved, list):
        return _default_roles()
    defaults = {row["key"]: row for row in _default_roles()}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in saved:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "").strip().lower()
        if not key or key in seen or not (key in defaults or _ROLE_KEY.match(key)):
            continue
        seen.add(key)
        base = defaults.get(key)
        caps = row.get("capabilities")
        caps = [c for c in caps if c in CAPABILITY_KEYS] if isinstance(caps, list) else list(base["capabilities"] if base else [])
        if key in LOCKED_ROLES:
            caps = list(CAPABILITY_KEYS)
        out.append(
            {
                "key": key,
                "name": str(row.get("name") or (base["name"] if base else key)).strip()[:MAX_NAME_LEN],
                "description": str(row.get("description") or (base["description"] if base else "")).strip()[:MAX_DESCRIPTION_LEN],
                "capabilities": [c for c in CAPABILITY_KEYS if c in caps],
                "custom": base is None,
            }
        )
    # Built in roles can't be removed, so put back any a stored copy lacks.
    for key in ORG_ROLES:
        if key not in seen:
            out.insert(ORG_ROLES.index(key), defaults[key])
    return out


def role_capabilities(org_settings: Any, role: str) -> frozenset[str]:
    """Capability keys one membership role holds in this workspace."""
    role = (role or "").strip().lower()
    if role == "owner" or role in LOCKED_ROLES:
        return frozenset(CAPABILITY_KEYS)
    for row in stored_role_definitions(org_settings):
        if row["key"] == role:
            return frozenset(row["capabilities"])
    return frozenset()


def _slug(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:32] or "role"
    if not base[0].isalpha():
        base = f"role_{base}"[:32]
    key, n = base, 2
    while key in taken or key in ("owner",):
        key, n = f"{base}_{n}", n + 1
    return key


def validate_role_definitions(roles: Any, *, member_counts: dict[str, int] | None = None, current: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Check a full replacement of the role list and return it in stored form."""
    if not isinstance(roles, list) or not roles:
        raise RolePermissionsError("Send at least one role.")
    if len(roles) > MAX_ROLES:
        raise RolePermissionsError(f"A workspace can have at most {MAX_ROLES} roles.")
    taken: set[str] = set()
    names: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in roles:
        if not isinstance(row, dict):
            raise RolePermissionsError("Each role must be an object.")
        name = str(row.get("name") or "").strip()
        if not name:
            raise RolePermissionsError("Every role needs a name.")
        if len(name) > MAX_NAME_LEN:
            raise RolePermissionsError(f"Role names can be at most {MAX_NAME_LEN} characters.")
        if name.lower() in names:
            raise RolePermissionsError(f"Two roles are named {name}.")
        names.add(name.lower())
        description = str(row.get("description") or "").strip()
        if len(description) > MAX_DESCRIPTION_LEN:
            raise RolePermissionsError(f"Role descriptions can be at most {MAX_DESCRIPTION_LEN} characters.")
        caps = row.get("capabilities")
        if not isinstance(caps, list):
            raise RolePermissionsError(f"{name} needs a list of capabilities.")
        unknown = sorted({str(c) for c in caps} - set(CAPABILITY_KEYS))
        if unknown:
            raise RolePermissionsError(f"Unknown capabilities: {', '.join(unknown)}")
        key = str(row.get("key") or "").strip().lower()
        if key in ORG_ROLES:
            if key in taken:
                raise RolePermissionsError(f"The {key} role is listed twice.")
        elif key:
            if not _ROLE_KEY.match(key) or key == "owner" or key in taken:
                raise RolePermissionsError(f"{name} has an invalid key.")
        else:
            key = _slug(name, taken | set(ORG_ROLES))
        taken.add(key)
        out.append(
            {
                "key": key,
                "name": name,
                "description": description,
                "capabilities": list(CAPABILITY_KEYS) if key in LOCKED_ROLES else [c for c in CAPABILITY_KEYS if c in caps],
            }
        )
    missing = [role for role in ORG_ROLES if role not in taken]
    if missing:
        raise RolePermissionsError(f"Built in roles can't be deleted: {', '.join(missing)}.")
    if current and member_counts:
        for row in current:
            if row["key"] not in taken and member_counts.get(row["key"], 0) > 0:
                raise RolePermissionsError(f"Move the people on {row['name']} to another role before deleting it.")
    return out


def get_org_role_permissions_matrix(org_settings: Any = None) -> dict[str, Any]:
    roles = stored_role_definitions(org_settings or {})
    keys = [row["key"] for row in roles]
    return {
        "roles": keys,
        "role_names": {row["key"]: row["name"] for row in roles},
        "role_descriptions": {row["key"]: row["description"] for row in roles},
        "custom_roles": [row["key"] for row in roles if row["custom"]],
        "locked_roles": [key for key in keys if key in LOCKED_ROLES],
        "capabilities": [
            {
                "key": cap["key"],
                "capability": cap["capability"],
                "area": cap.get("area"),
                "access": {row["key"]: cap["key"] in row["capabilities"] for row in roles},
            }
            for cap in ORG_ROLE_CAPABILITIES
        ],
    }


CAPABILITY_LABELS: dict[str, str] = {row["key"]: row["capability"] for row in ORG_ROLE_CAPABILITIES}


def load_org_settings(client: Any, org_id: str) -> dict[str, Any]:
    """organizations.settings for one org, or {} (the default matrix) when it can't be read."""
    try:
        rows = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute().data or []
    except Exception:  # noqa: BLE001
        return {}
    settings = rows[0].get("settings") if rows and isinstance(rows[0], dict) else None
    return settings if isinstance(settings, dict) else {}


def assignable_role_keys(org_settings: Any) -> frozenset[str]:
    """Roles people can be given in this workspace: the built in ones plus its custom roles."""
    return frozenset(row["key"] for row in stored_role_definitions(org_settings))


def membership_role(client: Any, org_id: str, user_id: str) -> str | None:
    rows = (
        client.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return None
    return str(rows[0].get("role") or "member").strip().lower()


def has_capability(client: Any, org_id: str, role: str | None, capability: str) -> bool:
    """Whether one membership role holds ``capability`` under this workspace's saved matrix."""
    role = (role or "").strip().lower()
    if not role:
        return False
    if role == "owner" or role in LOCKED_ROLES:
        return True
    return capability in role_capabilities(load_org_settings(client, org_id), role)


def capability_denied_detail(capability: str) -> str:
    label = CAPABILITY_LABELS.get(capability, capability).lower()
    return f"Your role doesn't allow this ({label}). Ask an admin to change it in Trust & Safety > Role permissions."

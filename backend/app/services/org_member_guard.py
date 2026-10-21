"""One authorization rule for changing or removing organization memberships.

Every endpoint that changes a member's role or removes a member calls
``assert_member_change_allowed`` before writing. The rules:

* the actor must be an owner or admin of the org, or hold the "team_roles"
  capability (Trust & Safety > Role permissions); such an actor can't change,
  remove or create owners and admins;
* the target must be a member of the same org (otherwise 404, so ids from other
  orgs reveal nothing);
* only an owner may change or remove an owner, or make someone an owner;
* an org that has an owner keeps at least one (older orgs created before the
  owner role may have only admins; they are not blocked by this rule);
* the org always keeps at least one owner or admin.

Ownership changes hands only through an explicit transfer by an owner.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status

from app.auth.org_role_permissions import capability_denied_detail, has_capability

OWNER = "owner"
ADMIN_ROLES = frozenset({"owner", "admin"})


@dataclass(frozen=True)
class MemberRow:
    id: str
    user_id: str
    role: str


def _role(value: Any) -> str:
    return str(value or "").strip().lower()


def load_member(client: Any, org_id: str, *, user_id: str | None = None, member_id: str | None = None) -> MemberRow | None:
    query = client.table("organization_members").select("id, user_id, role").eq("org_id", org_id)
    query = query.eq("id", member_id) if member_id else query.eq("user_id", user_id)
    rows = query.limit(1).execute().data or []
    if not rows:
        return None
    row = rows[0]
    return MemberRow(id=str(row.get("id")), user_id=str(row.get("user_id")), role=_role(row.get("role")))


def _org_roles(client: Any, org_id: str) -> list[tuple[str, str]]:
    rows = (
        client.table("organization_members").select("user_id, role").eq("org_id", org_id).execute().data or []
    )
    return [(str(r.get("user_id")), _role(r.get("role"))) for r in rows]


def _require_team_manager(client: Any, org_id: str, actor_user_id: str) -> MemberRow:
    actor = load_member(client, org_id, user_id=actor_user_id)
    if actor is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    if actor.role not in ADMIN_ROLES and not has_capability(client, org_id, actor.role, "team_roles"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=capability_denied_detail("team_roles"))
    return actor


def assert_invite_role_allowed(client: Any, org_id: str, *, actor_user_id: str, role: str) -> None:
    """Only owners and admins invite people as admins; others need team_roles and pick a lower role."""
    actor = _require_team_manager(client, org_id, actor_user_id)
    if actor.role not in ADMIN_ROLES and _role(role) in ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an owner or admin can invite admins")


def assert_member_change_allowed(
    client: Any,
    org_id: str,
    *,
    actor_user_id: str,
    target: MemberRow | None,
    new_role: str | None,
) -> MemberRow:
    """Raise HTTPException unless the actor may set ``target`` to ``new_role``.

    ``new_role=None`` means remove the member. Returns the target row.
    """
    actor = _require_team_manager(client, org_id, actor_user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    wanted = _role(new_role) if new_role is not None else None
    if actor.role not in ADMIN_ROLES and (target.role in ADMIN_ROLES or wanted in ADMIN_ROLES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an owner or admin can change admins")

    touches_owner = target.role == OWNER or wanted == OWNER
    if touches_owner and actor.role != OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an owner can change an owner")

    roles = _org_roles(client, org_id)
    after = [(uid, (wanted if uid == target.user_id else role)) for uid, role in roles if not (uid == target.user_id and wanted is None)]
    had_owner = any(role == OWNER for _uid, role in roles)
    if had_owner and not any(role == OWNER for _uid, role in after):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The organization must keep at least one owner; transfer ownership first",
        )
    if not any(role in ADMIN_ROLES for _uid, role in after):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The organization must keep at least one owner or admin",
        )
    return target

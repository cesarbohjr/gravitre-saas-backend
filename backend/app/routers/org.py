"""Organization and membership management endpoints."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client
from app.core.db import shared_service_client
from app.core.org_state_cache import invalidate_org_and_users, invalidate_org_state, invalidate_user_state

from app.auth.dependencies import get_current_user, get_org_context, require_admin, require_capability
from app.auth.org_role_permissions import (
    ROLE_PERMISSIONS_SETTINGS_KEY,
    RolePermissionsError,
    assignable_role_keys,
    capability_denied_detail,
    get_org_role_permissions_matrix,
    has_capability,
    load_org_settings,
    membership_role,
    role_capabilities,
    stored_role_definitions,
    validate_role_definitions,
)
from app.config import Settings, get_settings
from app.billing.service import DEFAULT_PLANS, PLAN_CODE_ALIASES
from app.services.org_member_invite_service import (
    _invite_redirect_url as invite_redirect_url,
    invite_org_member_by_email,
    normalize_org_member_role,
)
from app.workflows.audit import write_audit_event
from app.services.org_member_guard import assert_invite_role_allowed, assert_member_change_allowed, load_member

router = APIRouter(prefix="/api/org", tags=["org"])
organizations_router = APIRouter(prefix="/api/organizations", tags=["organizations"])

RESOURCE_TYPE_ORG_MEMBER = "org_member"
AUDIT_ORG_MEMBER_LISTED = "org.member.listed"
AUDIT_ORG_MEMBER_INVITED = "org.member.invited"
AUDIT_ORG_MEMBER_UPDATED = "org.member.updated"
AUDIT_ORG_MEMBER_REMOVED = "org.member.removed"
AUDIT_ORG_MEMBER_INVITE_RESENT = "org.member.invite_resent"


# Built in roles or a custom role key from Trust & Safety > Role permissions; the
# endpoint checks the role exists in this workspace.
class PatchMemberRequest(BaseModel):
    role: str = Field(..., pattern="^[a-z][a-z0-9_]{0,39}$")


class InviteRequest(BaseModel):
    email: str | None = Field(default=None, description="Optional; stub does not send email")


class OrganizationCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=80)


class OrganizationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=80)
    logo_url: str | None = None
    plan: str | None = None


class OrganizationMemberInviteRequest(BaseModel):
    email: str = Field(..., min_length=3)
    role: str = Field(default="member", pattern="^[a-z][a-z0-9_]{0,39}$")
    send_invite: bool = Field(default=True, description="Send Supabase invite email")


class OrganizationMemberRoleRequest(BaseModel):
    role: str = Field(..., pattern="^[a-z][a-z0-9_]{0,39}$")


class TransferOwnershipRequest(BaseModel):
    new_owner_id: str = Field(..., min_length=1)


def _slugify(value: str) -> str:
    slug = value.strip().lower()
    cleaned: list[str] = []
    prev_dash = False
    for ch in slug:
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            cleaned.append(ch)
            prev_dash = False
        elif not prev_dash:
            cleaned.append("-")
            prev_dash = True
    normalized = "".join(cleaned).strip("-")
    return normalized or "organization"


def _is_member(client, org_id: str, user_id: str) -> bool:
    membership = (
        client.table("organization_members")
        .select("id")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return bool(membership.data)


def _require_org_member(client, org_id: str, user_id: str) -> None:
    if not _is_member(client, org_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this organization")


def _require_org_capability(client, org_id: str, user_id: str, capability: str) -> None:
    """Owners and admins, or a member whose role holds ``capability`` in this workspace."""
    role = membership_role(client, org_id, user_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this organization")
    if not has_capability(client, org_id, role, capability):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=capability_denied_detail(capability))


def _write_member_role(write) -> None:
    """Run a role update; a custom role before the custom-roles migration is a clear 409, not a 500."""
    try:
        write()
    except Exception as exc:  # noqa: BLE001
        if "organization_members_role_check" in str(exc) or "23514" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This workspace can't put people on custom roles until the custom roles database update is applied.",
            ) from exc
        raise


def _assert_assignable_role(client, org_id: str, role: str) -> str:
    """The role key if people can be given it here (built in or one of this workspace's custom roles)."""
    normalized = (role or "").strip().lower()
    if normalized not in assignable_role_keys(load_org_settings(client, org_id)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown role: {normalized}")
    return normalized


def _normalize_org_row(row: dict) -> dict:
    settings = row.get("settings") if isinstance(row.get("settings"), dict) else {}
    # organizations has no plan/logo_url columns — derive from settings when present.
    return {
        "id": str(row.get("id")),
        "name": row.get("name"),
        "slug": row.get("slug"),
        "logo_url": row.get("logo_url") or settings.get("logoUrl") or settings.get("logo_url"),
        "plan": row.get("plan") or settings.get("plan") or settings.get("planCode"),
        "created_at": row.get("created_at"),
    }


@router.get("/members")
def list_members(
    _admin: Annotated[tuple, Depends(require_capability("team_roles"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """List org members. Admin only."""
    _user, org_id = _admin
    client = shared_service_client(settings, create_client)
    r = (
        client.table("organization_members")
        .select("id, user_id, role, created_at")
        .eq("org_id", org_id)
        .execute()
    )
    members = [
        {
            "id": str(m["id"]),
            "user_id": str(m["user_id"]),
            "role": m["role"],
            "created_at": m["created_at"],
        }
        for m in (r.data or [])
    ]
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action=AUDIT_ORG_MEMBER_LISTED,
        resource_type=RESOURCE_TYPE_ORG_MEMBER,
        resource_id=org_id,
        metadata={"count": len(members)},
    )
    return {"members": members}


def _member_role_counts(client, org_id: str) -> dict[str, int] | None:
    """People per membership role in one org (owner kept apart from admin)."""
    try:
        rows = client.table("organization_members").select("role").eq("org_id", org_id).execute()
    except Exception:  # noqa: BLE001
        return None
    counts = {"owner": 0, "admin": 0, "member": 0, "viewer": 0}
    for row in rows.data or []:
        role = str(row.get("role") or "member").strip().lower() or "member"
        counts[role] = counts.get(role, 0) + 1
    return counts


def _org_settings_row(client, org_id: str) -> dict:
    row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    value = row.data[0].get("settings") or {}
    return value if isinstance(value, dict) else {}


@router.get("/role-permissions")
def get_role_permissions(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Return this workspace's role capability matrix, plus people per role."""
    if not org_id:
        matrix = get_org_role_permissions_matrix()
        matrix["member_counts"] = None
        return matrix
    client = shared_service_client(settings, create_client)
    try:
        org_settings = _org_settings_row(client, org_id)
    except Exception:  # noqa: BLE001 - fall back to the default roles
        org_settings = {}
    matrix = get_org_role_permissions_matrix(org_settings)
    matrix["member_counts"] = _member_role_counts(client, org_id)
    try:
        my_role = membership_role(client, org_id, str(_user.get("user_id") or ""))
    except Exception:  # noqa: BLE001 - the matrix still renders without the caller's row
        my_role = None
    matrix["my_role"] = my_role
    matrix["my_capabilities"] = sorted(role_capabilities(org_settings, my_role)) if my_role else []
    return matrix


class RoleDefinitionBody(BaseModel):
    key: str | None = Field(default=None, max_length=40)
    name: str = Field(min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=160)
    capabilities: list[str] = Field(default_factory=list, max_length=50)


class RolePermissionsUpdate(BaseModel):
    roles: list[RoleDefinitionBody] = Field(min_length=1, max_length=20)


@router.put("/role-permissions")
def update_role_permissions(
    body: RolePermissionsUpdate,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Replace this workspace's roles: capabilities per role, new roles and removed ones."""
    user, org_id = admin
    client = shared_service_client(settings, create_client)
    org_settings = _org_settings_row(client, org_id)
    current = stored_role_definitions(org_settings)
    counts = _member_role_counts(client, org_id)
    try:
        roles = validate_role_definitions(
            [row.model_dump() for row in body.roles], member_counts=counts, current=current
        )
    except RolePermissionsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    org_settings[ROLE_PERMISSIONS_SETTINGS_KEY] = {"roles": roles}
    updated = client.table("organizations").update({"settings": org_settings}).eq("id", org_id).execute()
    invalidate_org_state(org_id)
    if not updated.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    before = {row["key"]: row["capabilities"] for row in current}
    after = {row["key"]: row["capabilities"] for row in roles}
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action="settings.role_permissions.updated",
        resource_type="organization",
        resource_id=org_id,
        metadata={
            "added_roles": sorted(set(after) - set(before)),
            "removed_roles": sorted(set(before) - set(after)),
            "changed_roles": sorted(k for k in set(after) & set(before) if after[k] != before[k]),
        },
    )
    matrix = get_org_role_permissions_matrix(updated.data[0].get("settings") or org_settings)
    matrix["member_counts"] = counts
    return matrix


def _auth_invite_state(client, user_id: str) -> dict | None:
    """Invite state of one auth user: pending until the invite link is accepted."""
    try:
        response = client.auth.admin.get_user_by_id(user_id)
    except Exception:  # noqa: BLE001
        return None
    user = getattr(response, "user", None)
    if user is None and isinstance(response, dict):
        user = response.get("user", response)
    if user is None:
        return None

    def _get(name: str):
        return user.get(name) if isinstance(user, dict) else getattr(user, name, None)

    def _iso(value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value if isinstance(value, str) and value else None

    invited_at = _iso(_get("invited_at"))
    confirmed_at = _iso(_get("email_confirmed_at")) or _iso(_get("confirmed_at"))
    last_sign_in_at = _iso(_get("last_sign_in_at"))
    return {
        "user_id": user_id,
        "email": _get("email") if isinstance(_get("email"), str) else None,
        "invited_at": invited_at,
        "last_sign_in_at": last_sign_in_at,
        "pending": bool(invited_at) and not confirmed_at and not last_sign_in_at,
    }


MAX_INVITE_STATE_LOOKUPS = 200


@router.get("/invites")
def list_pending_invites(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Members of this org who were invited and have not accepted yet.

    Invites attach the membership right away (org_member_invite_service), so
    "pending" is read from the invited auth user: invited, never confirmed and
    never signed in.
    """
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = shared_service_client(settings, create_client)
    _require_org_member(client, org_id, current_user["user_id"])
    rows = (
        client.table("organization_members")
        .select("user_id, role, created_at")
        .eq("org_id", org_id)
        .execute()
    ).data or []
    members = [row for row in rows if row.get("user_id")]
    checked = members[:MAX_INVITE_STATE_LOOKUPS]
    with ThreadPoolExecutor(max_workers=8) as pool:
        states = list(pool.map(lambda row: _auth_invite_state(client, str(row["user_id"])), checked))
    invites = []
    unknown = 0
    for row, state in zip(checked, states):
        if state is None:
            unknown += 1
            continue
        if state["pending"]:
            invites.append(
                {
                    "user_id": str(row["user_id"]),
                    "email": state["email"],
                    "role": normalize_org_member_role(row.get("role")),
                    "invited_at": state["invited_at"] or row.get("created_at"),
                }
            )
    return {
        "invites": invites,
        "checked": len(checked) - unknown,
        "unchecked": unknown + max(0, len(members) - len(checked)),
    }


@router.post("/invites/{user_id}/resend")
def resend_invite(
    user_id: UUID,
    _admin: Annotated[tuple, Depends(require_capability("team_roles"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Send the invite email again to a member who has not accepted yet. Admin only."""
    _user, org_id = _admin
    target_id = str(user_id)
    client = shared_service_client(settings, create_client)
    member = load_member(client, org_id, user_id=target_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    state = _auth_invite_state(client, target_id)
    if state is None or not state.get("email"):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to read this invite. Try again.")
    if not state["pending"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This person already accepted the invite")
    try:
        client.auth.admin.invite_user_by_email(
            state["email"],
            {
                "redirect_to": invite_redirect_url(settings),
                "data": {
                    "invited_org_id": org_id,
                    "invited_role": member.role,
                    "invite_context": "organization_members_invite_resend",
                    "invited_by": _user["user_id"],
                },
            },
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Unable to send invite email: {exc}") from exc
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action=AUDIT_ORG_MEMBER_INVITE_RESENT,
        resource_type=RESOURCE_TYPE_ORG_MEMBER,
        resource_id=member.id,
        metadata={"email": state["email"], "role": member.role},
    )
    return {"ok": True, "email": state["email"]}


@router.post("/members/invite")
def invite_member(
    body: InviteRequest,
    _admin: Annotated[tuple, Depends(require_capability("team_roles"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Stub: create invite token (no email sent). Admin only."""
    _user, org_id = _admin
    client = shared_service_client(settings, create_client)
    token = f"stub-invite-{org_id[:8]}-{_user['user_id'][:8]}"
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action=AUDIT_ORG_MEMBER_INVITED,
        resource_type=RESOURCE_TYPE_ORG_MEMBER,
        resource_id=org_id,
        metadata={"invite_stub": True, "email_provided": body.email is not None},
    )
    return {"invite_token": token, "message": "Invite created (stub); no email sent"}


@router.patch("/members/{member_id}")
def update_member(
    member_id: UUID,
    body: PatchMemberRequest,
    _admin: Annotated[tuple, Depends(require_capability("team_roles"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Update member role. Owner/admin only; owners change only by an owner; the org keeps an owner and an admin."""
    _user, org_id = _admin
    mid = str(member_id)
    client = shared_service_client(settings, create_client)
    target = load_member(client, org_id, member_id=mid)
    if target is not None and target.role == body.role:
        return {"id": mid, "user_id": target.user_id, "role": body.role}
    _assert_assignable_role(client, org_id, body.role)
    target = assert_member_change_allowed(
        client, org_id, actor_user_id=_user["user_id"], target=target, new_role=body.role
    )

    _write_member_role(lambda: client.table("organization_members").update({"role": body.role}).eq("id", mid).eq("org_id", org_id).execute())
    invalidate_org_and_users(org_id, [target.user_id])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action=AUDIT_ORG_MEMBER_UPDATED,
        resource_type=RESOURCE_TYPE_ORG_MEMBER,
        resource_id=mid,
        metadata={"old_role": target.role, "new_role": body.role},
    )
    return {"id": mid, "user_id": target.user_id, "role": body.role}


@router.delete("/members/{member_id}")
def remove_member(
    member_id: UUID,
    _admin: Annotated[tuple, Depends(require_capability("team_roles"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Remove member from org. Owner/admin only; owners removed only by an owner; the org keeps an owner and an admin."""
    _user, org_id = _admin
    mid = str(member_id)
    client = shared_service_client(settings, create_client)
    target = assert_member_change_allowed(
        client,
        org_id,
        actor_user_id=_user["user_id"],
        target=load_member(client, org_id, member_id=mid),
        new_role=None,
    )

    client.table("organization_members").delete().eq("id", mid).eq("org_id", org_id).execute()
    invalidate_org_and_users(org_id, [target.user_id])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action=AUDIT_ORG_MEMBER_REMOVED,
        resource_type=RESOURCE_TYPE_ORG_MEMBER,
        resource_id=mid,
        metadata={"removed_user_id": target.user_id, "role": target.role},
    )
    return {"removed": True, "id": mid}


@organizations_router.get("")
def list_organizations(
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = shared_service_client(settings, create_client)
    memberships = (
        client.table("organization_members")
        .select("org_id, role")
        .eq("user_id", current_user["user_id"])
        .execute()
    )
    if not memberships.data:
        return {"organizations": []}

    roles_by_org = {str(item["org_id"]): (item.get("role") or "member") for item in memberships.data}
    org_ids = list(roles_by_org.keys())
    orgs = client.table("organizations").select("id, name, slug, settings, created_at").in_("id", org_ids).execute()
    rows = [_normalize_org_row(row) for row in (orgs.data or [])]
    plans = _org_plans(client, [row["id"] for row in rows])
    counts = _org_counts(client, [row["id"] for row in rows])
    for row in rows:
        row["role"] = roles_by_org.get(row["id"], "member")
        plan = plans.get(row["id"])
        if plan:
            row.update(plan)
        else:
            row.update({"plan_code": None, "plan_name": None, "plan_status": None})
        row.update(counts.get(row["id"], {}))
    return {"organizations": rows}


ORG_COUNT_TABLES: tuple[tuple[str, str], ...] = (
    ("member_count", "organization_members"),
    ("agent_count", "agents"),
    ("workflow_count", "workflows"),
)
MAX_COUNTED_ORGS = 50


def _plan_name(plan_code: str | None) -> str | None:
    code = str(plan_code or "").strip().lower()
    if not code:
        return None
    plan = DEFAULT_PLANS.get(code) or DEFAULT_PLANS.get(PLAN_CODE_ALIASES.get(code, ""))
    return str(plan["name"]) if plan and plan.get("name") else code.title()


def _org_plans(client, org_ids: list[str]) -> dict[str, dict]:
    """Plan on record per org from org_billing, in one query."""
    if not org_ids:
        return {}
    try:
        resp = client.table("org_billing").select("org_id, plan_code, billing_status").in_("org_id", org_ids).execute()
    except Exception:  # noqa: BLE001
        return {}
    plans: dict[str, dict] = {}
    for row in resp.data or []:
        code = str(row.get("plan_code") or "").strip().lower() or None
        plans[str(row.get("org_id"))] = {
            "plan_code": code,
            "plan_name": _plan_name(code),
            "plan_status": row.get("billing_status"),
        }
    return plans


def _exact_count(client, table: str, org_id: str) -> int | None:
    try:
        resp = client.table(table).select("id", count="exact").eq("org_id", org_id).limit(1).execute()
    except Exception:  # noqa: BLE001
        return None
    count = getattr(resp, "count", None)
    return int(count) if isinstance(count, int) else None


def _org_counts(client, org_ids: list[str]) -> dict[str, dict]:
    """Members, agents and workflows per org as exact counts (no rows fetched).

    None means the count could not be read, never zero. Counts run in parallel
    and only for the first MAX_COUNTED_ORGS orgs.
    """
    jobs = [(org_id, key, table) for org_id in org_ids[:MAX_COUNTED_ORGS] for key, table in ORG_COUNT_TABLES]
    result: dict[str, dict] = {org_id: {key: None for key, _ in ORG_COUNT_TABLES} for org_id in org_ids}
    if not jobs:
        return result
    with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as pool:
        values = list(pool.map(lambda job: _exact_count(client, job[2], job[0]), jobs))
    for (org_id, key, _table), value in zip(jobs, values):
        result[org_id][key] = value
    return result


@organizations_router.get("/{org_id}")
def get_organization(
    org_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    client = shared_service_client(settings, create_client)
    _require_org_member(client, org_id_str, current_user["user_id"])
    org = (
        client.table("organizations")
        .select("id, name, slug, settings, created_at")
        .eq("id", org_id_str)
        .limit(1)
        .execute()
    )
    if not org.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return _normalize_org_row(org.data[0])


@organizations_router.post("")
def create_organization(
    body: OrganizationCreateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = shared_service_client(settings, create_client)
    slug = _slugify(body.slug or body.name)
    # Bug fix (2026-09-12): postgrest-py's SyncQueryRequestBuilder (the type
    # returned by .insert()) has no .select()/.limit() method — chaining them
    # here raised an uncaught AttributeError on every call, surfaced to the
    # client as a generic 500 "unexpected error" (via the global exception
    # handler in app/main.py). .insert() already returns the full row by
    # default (returning=representation), so no .select() chain is needed —
    # matches the plain insert().execute() pattern used everywhere else in
    # this codebase (e.g. routers/sources.py, routers/workflows.py).
    created = (
        client.table("organizations")
        .insert({"name": body.name.strip(), "slug": slug, "status": "active"})
        .execute()
    )
    if not created.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to create organization")
    org_row = created.data[0]
    org_id = str(org_row["id"])
    client.table("organization_members").insert(
        {"id": str(uuid4()), "org_id": org_id, "user_id": current_user["user_id"], "role": "owner"}
    ).execute()
    invalidate_org_and_users(org_id, [current_user["user_id"]])
    return _normalize_org_row(org_row)


@organizations_router.patch("/{org_id}")
def update_organization(
    org_id: UUID,
    body: OrganizationUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    client = shared_service_client(settings, create_client)
    _require_org_capability(client, org_id_str, current_user["user_id"], "org_settings_billing")

    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    # The plan is set by billing, never by an org admin through this endpoint.
    payload.pop("plan", None)
    if "slug" in payload:
        payload["slug"] = _slugify(payload["slug"])
    if not payload:
        existing = (
            client.table("organizations")
            .select("id, name, slug, settings, created_at")
            .eq("id", org_id_str)
            .limit(1)
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
        return _normalize_org_row(existing.data[0])

    # Bug fix (2026-09-12): same root cause as create_organization above —
    # postgrest-py's SyncFilterRequestBuilder (returned by .update().eq())
    # has no .select()/.limit() method. .update() already returns the full
    # row by default (returning=representation).
    updated = (
        client.table("organizations")
        .update(payload)
        .eq("id", org_id_str)
        .execute()
    )
    invalidate_org_state(org_id_str)
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return _normalize_org_row(updated.data[0])


@organizations_router.delete("/{org_id}")
def delete_organization(
    org_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    client = shared_service_client(settings, create_client)
    # Deleting the organization is an owner decision, not an admin one.
    actor = load_member(client, org_id_str, user_id=current_user["user_id"])
    if actor is None or actor.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an owner can delete the organization")
    client.table("organizations").delete().eq("id", org_id_str).execute()
    invalidate_org_and_users(org_id_str, [current_user["user_id"]])
    return {"ok": True}


@organizations_router.post("/{org_id}/switch")
def switch_organization(
    org_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    client = shared_service_client(settings, create_client)
    _require_org_member(client, org_id_str, current_user["user_id"])
    # The selected org changes what /api/auth/me reports for this user.
    invalidate_user_state(current_user["user_id"])

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": current_user["user_id"],
            "email": current_user.get("email"),
            "aud": settings.jwt_audience,
            "iss": settings.jwt_issuer,
            "org_id": org_id_str,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    return {"token": token}


@organizations_router.get("/{org_id}/members")
def list_organization_members(
    org_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    client = shared_service_client(settings, create_client)
    _require_org_member(client, org_id_str, current_user["user_id"])
    membership_rows = (
        client.table("organization_members")
        .select("user_id, role")
        .eq("org_id", org_id_str)
        .execute()
    )
    members: list[dict] = []
    for row in membership_rows.data or []:
        # organization_members.user_id is the auth UID; public.users links via auth_user_id.
        auth_user_id = str(row["user_id"])
        user_resp = (
            client.table("users")
            .select(
                "id, auth_user_id, email, full_name, avatar_url, "
                "job_title, department, created_at, updated_at"
            )
            .eq("auth_user_id", auth_user_id)
            .limit(1)
            .execute()
        )
        user = (user_resp.data or [{}])[0]
        members.append(
            {
                "id": str(user.get("id") or auth_user_id),
                "user_id": auth_user_id,
                "email": user.get("email"),
                "full_name": user.get("full_name"),
                "avatar_url": user.get("avatar_url"),
                "job_title": user.get("job_title"),
                "department": user.get("department"),
                "created_at": user.get("created_at"),
                "updated_at": user.get("updated_at"),
                "role": row.get("role") or "member",
            }
        )
    return {"members": members}


@organizations_router.post("/{org_id}/members/invite")
async def invite_organization_member(
    org_id: UUID,
    body: OrganizationMemberInviteRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    client = shared_service_client(settings, create_client)
    _require_org_capability(client, org_id_str, current_user["user_id"], "team_roles")
    role = _assert_assignable_role(client, org_id_str, body.role)
    assert_invite_role_allowed(client, org_id_str, actor_user_id=current_user["user_id"], role=role)
    invite_result = invite_org_member_by_email(
        client,
        settings,
        org_id=org_id_str,
        email=body.email,
        role=role,
        invited_by_user_id=current_user["user_id"],
        send_invite=body.send_invite,
        invite_context="organization_members_invite",
    )
    write_audit_event(
        client,
        org_id=org_id_str,
        actor_id=current_user["user_id"],
        action=AUDIT_ORG_MEMBER_INVITED,
        resource_type=RESOURCE_TYPE_ORG_MEMBER,
        resource_id=invite_result["user_id"],
        metadata={
            "email": invite_result["email"],
            "role": invite_result["role"],
            "invite_email_sent": invite_result["invite_email_sent"],
            "invite_email_status": invite_result["invite_email_status"],
            "membership_created": invite_result["membership_created"],
        },
    )
    return {"ok": True, "member": invite_result}


@organizations_router.patch("/{org_id}/members/{user_id}")
def update_organization_member_role(
    org_id: UUID,
    user_id: UUID,
    body: OrganizationMemberRoleRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    member_user_id = str(user_id)
    client = shared_service_client(settings, create_client)
    _assert_assignable_role(client, org_id_str, body.role)
    target = assert_member_change_allowed(
        client,
        org_id_str,
        actor_user_id=current_user["user_id"],
        target=load_member(client, org_id_str, user_id=member_user_id),
        new_role=body.role,
    )
    _write_member_role(
        lambda: client.table("organization_members").update({"role": body.role}).eq("org_id", org_id_str).eq(
            "user_id", member_user_id
        ).execute()
    )
    invalidate_org_and_users(org_id_str, [member_user_id])
    write_audit_event(
        client,
        org_id=org_id_str,
        actor_id=current_user["user_id"],
        action=AUDIT_ORG_MEMBER_UPDATED,
        resource_type=RESOURCE_TYPE_ORG_MEMBER,
        resource_id=target.id,
        metadata={"old_role": target.role, "new_role": body.role},
    )
    return {"ok": True}


@organizations_router.delete("/{org_id}/members/{user_id}")
def remove_organization_member(
    org_id: UUID,
    user_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    member_user_id = str(user_id)
    client = shared_service_client(settings, create_client)
    target = assert_member_change_allowed(
        client,
        org_id_str,
        actor_user_id=current_user["user_id"],
        target=load_member(client, org_id_str, user_id=member_user_id),
        new_role=None,
    )
    client.table("organization_members").delete().eq("org_id", org_id_str).eq("user_id", member_user_id).execute()
    invalidate_org_and_users(org_id_str, [member_user_id])
    write_audit_event(
        client,
        org_id=org_id_str,
        actor_id=current_user["user_id"],
        action=AUDIT_ORG_MEMBER_REMOVED,
        resource_type=RESOURCE_TYPE_ORG_MEMBER,
        resource_id=target.id,
        metadata={"removed_user_id": member_user_id, "role": target.role},
    )
    return {"ok": True}


@organizations_router.post("/{org_id}/transfer")
def transfer_organization_ownership(
    org_id: UUID,
    body: TransferOwnershipRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """An owner hands ownership to another member: they become owner, the caller becomes admin.

    Previously any admin could call this, and it set the new "owner" to admin and
    the caller to member, so ownership never moved and an admin could demote
    themselves while promoting someone else to admin.
    """
    org_id_str = str(org_id)
    client = shared_service_client(settings, create_client)
    actor = load_member(client, org_id_str, user_id=current_user["user_id"])
    if actor is None or actor.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an owner can transfer ownership")
    new_owner = load_member(client, org_id_str, user_id=body.new_owner_id)
    if new_owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if new_owner.user_id == actor.user_id:
        return {"ok": True}

    client.table("organization_members").update({"role": "owner"}).eq("org_id", org_id_str).eq(
        "user_id", new_owner.user_id
    ).execute()
    client.table("organization_members").update({"role": "admin"}).eq("org_id", org_id_str).eq(
        "user_id", actor.user_id
    ).execute()
    invalidate_org_and_users(org_id_str, [new_owner.user_id, actor.user_id])
    write_audit_event(
        client,
        org_id=org_id_str,
        actor_id=actor.user_id,
        action=AUDIT_ORG_MEMBER_UPDATED,
        resource_type=RESOURCE_TYPE_ORG_MEMBER,
        resource_id=new_owner.id,
        metadata={"ownership_transfer": True, "from_user_id": actor.user_id, "to_user_id": new_owner.user_id},
    )
    return {"ok": True}


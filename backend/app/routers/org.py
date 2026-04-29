"""Organization and membership management endpoints."""
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, require_admin
from app.config import Settings, get_settings
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/org", tags=["org"])
organizations_router = APIRouter(prefix="/api/organizations", tags=["organizations"])

RESOURCE_TYPE_ORG_MEMBER = "org_member"
AUDIT_ORG_MEMBER_LISTED = "org.member.listed"
AUDIT_ORG_MEMBER_INVITED = "org.member.invited"
AUDIT_ORG_MEMBER_UPDATED = "org.member.updated"
AUDIT_ORG_MEMBER_REMOVED = "org.member.removed"


class PatchMemberRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|member)$")


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
    role: str = Field(default="member", pattern="^(admin|member)$")


class OrganizationMemberRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|member)$")


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


def _is_admin(client, org_id: str, user_id: str) -> bool:
    membership = (
        client.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not membership.data:
        return False
    return (membership.data[0].get("role") or "").strip().lower() == "admin"


def _require_org_member(client, org_id: str, user_id: str) -> None:
    if not _is_member(client, org_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this organization")


def _require_org_admin(client, org_id: str, user_id: str) -> None:
    if not _is_admin(client, org_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


def _normalize_org_row(row: dict) -> dict:
    return {
        "id": str(row.get("id")),
        "name": row.get("name"),
        "slug": row.get("slug"),
        "logo_url": row.get("logo_url"),
        "plan": row.get("plan"),
        "created_at": row.get("created_at"),
    }


@router.get("/members")
async def list_members(
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """List org members. Admin only."""
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
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


@router.post("/members/invite")
async def invite_member(
    body: InviteRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Stub: create invite token (no email sent). Admin only."""
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
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
async def update_member(
    member_id: UUID,
    body: PatchMemberRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Update member role. Admin only. Cannot demote self if last admin."""
    _user, org_id = _admin
    mid = str(member_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    existing = (
        client.table("organization_members")
        .select("id, user_id, role")
        .eq("id", mid)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not existing.data or len(existing.data) == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    row = existing.data[0]
    if row["role"] == body.role:
        return {"id": mid, "user_id": str(row["user_id"]), "role": body.role}

    if str(row["user_id"]) == _user["user_id"] and body.role != "admin":
        admins = (
            client.table("organization_members")
            .select("id")
            .eq("org_id", org_id)
            .eq("role", "admin")
            .execute()
        )
        if len(admins.data or []) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote yourself; you are the only admin",
            )

    client.table("organization_members").update({"role": body.role}).eq("id", mid).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action=AUDIT_ORG_MEMBER_UPDATED,
        resource_type=RESOURCE_TYPE_ORG_MEMBER,
        resource_id=mid,
        metadata={"old_role": row["role"], "new_role": body.role},
    )
    return {"id": mid, "user_id": str(row["user_id"]), "role": body.role}


@router.delete("/members/{member_id}")
async def remove_member(
    member_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Remove member from org. Admin only. Cannot remove self if last admin."""
    _user, org_id = _admin
    mid = str(member_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    existing = (
        client.table("organization_members")
        .select("id, user_id")
        .eq("id", mid)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not existing.data or len(existing.data) == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    row = existing.data[0]
    if str(row["user_id"]) == _user["user_id"]:
        admins = (
            client.table("organization_members")
            .select("id")
            .eq("org_id", org_id)
            .eq("role", "admin")
            .execute()
        )
        if len(admins.data or []) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove yourself; you are the only admin",
            )

    client.table("organization_members").delete().eq("id", mid).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action=AUDIT_ORG_MEMBER_REMOVED,
        resource_type=RESOURCE_TYPE_ORG_MEMBER,
        resource_id=mid,
        metadata={"removed_user_id": str(row["user_id"])},
    )
    return {"id": mid, "message": "Member removed"}


@organizations_router.get("")
async def list_organizations(
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
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
    orgs = client.table("organizations").select("id, name, slug, logo_url, plan, created_at").in_("id", org_ids).execute()
    rows = [_normalize_org_row(row) for row in (orgs.data or [])]
    for row in rows:
        row["role"] = roles_by_org.get(row["id"], "member")
    return {"organizations": rows}


@organizations_router.get("/{org_id}")
async def get_organization(
    org_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _require_org_member(client, org_id_str, current_user["user_id"])
    org = (
        client.table("organizations")
        .select("id, name, slug, logo_url, plan, created_at")
        .eq("id", org_id_str)
        .limit(1)
        .execute()
    )
    if not org.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return _normalize_org_row(org.data[0])


@organizations_router.post("")
async def create_organization(
    body: OrganizationCreateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    slug = _slugify(body.slug or body.name)
    created = (
        client.table("organizations")
        .insert({"name": body.name.strip(), "slug": slug, "status": "active"})
        .select("id, name, slug, logo_url, plan, created_at")
        .limit(1)
        .execute()
    )
    if not created.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to create organization")
    org_row = created.data[0]
    org_id = str(org_row["id"])
    client.table("organization_members").insert(
        {"id": str(uuid4()), "org_id": org_id, "user_id": current_user["user_id"], "role": "admin"}
    ).execute()
    return _normalize_org_row(org_row)


@organizations_router.patch("/{org_id}")
async def update_organization(
    org_id: UUID,
    body: OrganizationUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _require_org_admin(client, org_id_str, current_user["user_id"])

    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    if "slug" in payload:
        payload["slug"] = _slugify(payload["slug"])
    if not payload:
        existing = (
            client.table("organizations")
            .select("id, name, slug, logo_url, plan, created_at")
            .eq("id", org_id_str)
            .limit(1)
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
        return _normalize_org_row(existing.data[0])

    updated = (
        client.table("organizations")
        .update(payload)
        .eq("id", org_id_str)
        .select("id, name, slug, logo_url, plan, created_at")
        .limit(1)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return _normalize_org_row(updated.data[0])


@organizations_router.delete("/{org_id}")
async def delete_organization(
    org_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _require_org_admin(client, org_id_str, current_user["user_id"])
    client.table("organizations").delete().eq("id", org_id_str).execute()
    return {"ok": True}


@organizations_router.post("/{org_id}/switch")
async def switch_organization(
    org_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _require_org_member(client, org_id_str, current_user["user_id"])

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
async def list_organization_members(
    org_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _require_org_member(client, org_id_str, current_user["user_id"])
    membership_rows = (
        client.table("organization_members")
        .select("user_id, role")
        .eq("org_id", org_id_str)
        .execute()
    )
    members: list[dict] = []
    for row in membership_rows.data or []:
        user_id = str(row["user_id"])
        user_resp = (
            client.table("users")
            .select("id, email, full_name, avatar_url, created_at, updated_at")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        user = (user_resp.data or [{}])[0]
        members.append(
            {
                "id": user_id,
                "email": user.get("email"),
                "full_name": user.get("full_name"),
                "avatar_url": user.get("avatar_url"),
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
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _require_org_admin(client, org_id_str, current_user["user_id"])

    user_lookup = (
        client.table("users")
        .select("id, auth_user_id, email")
        .eq("email", body.email.lower().strip())
        .limit(1)
        .execute()
    )
    if user_lookup.data:
        user = user_lookup.data[0]
        member_user_id = str(user.get("auth_user_id") or user.get("id"))
        already_member = _is_member(client, org_id_str, member_user_id)
        if not already_member:
            client.table("organization_members").insert(
                {
                    "id": str(uuid4()),
                    "org_id": org_id_str,
                    "user_id": member_user_id,
                    "role": body.role,
                }
            ).execute()
    return {"ok": True}


@organizations_router.patch("/{org_id}/members/{user_id}")
async def update_organization_member_role(
    org_id: UUID,
    user_id: UUID,
    body: OrganizationMemberRoleRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    member_user_id = str(user_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _require_org_admin(client, org_id_str, current_user["user_id"])
    updated = (
        client.table("organization_members")
        .update({"role": body.role})
        .eq("org_id", org_id_str)
        .eq("user_id", member_user_id)
        .select("user_id, role")
        .limit(1)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return {"ok": True}


@organizations_router.delete("/{org_id}/members/{user_id}")
async def remove_organization_member(
    org_id: UUID,
    user_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    member_user_id = str(user_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _require_org_admin(client, org_id_str, current_user["user_id"])
    client.table("organization_members").delete().eq("org_id", org_id_str).eq("user_id", member_user_id).execute()
    return {"ok": True}


@organizations_router.post("/{org_id}/transfer")
async def transfer_organization_ownership(
    org_id: UUID,
    body: TransferOwnershipRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id_str = str(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _require_org_admin(client, org_id_str, current_user["user_id"])
    _require_org_member(client, org_id_str, body.new_owner_id)

    client.table("organization_members").update({"role": "admin"}).eq("org_id", org_id_str).eq(
        "user_id", body.new_owner_id
    ).execute()
    if body.new_owner_id != current_user["user_id"]:
        client.table("organization_members").update({"role": "member"}).eq("org_id", org_id_str).eq(
            "user_id", current_user["user_id"]
        ).execute()
    return {"ok": True}

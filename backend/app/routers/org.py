"""RB-00: Org members and role management. Admin-only for mutations."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/org", tags=["org"])

RESOURCE_TYPE_ORG_MEMBER = "org_member"
AUDIT_ORG_MEMBER_LISTED = "org.member.listed"
AUDIT_ORG_MEMBER_INVITED = "org.member.invited"
AUDIT_ORG_MEMBER_UPDATED = "org.member.updated"
AUDIT_ORG_MEMBER_REMOVED = "org.member.removed"


class PatchMemberRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|member)$")


class InviteRequest(BaseModel):
    email: str | None = Field(default=None, description="Optional; stub does not send email")


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

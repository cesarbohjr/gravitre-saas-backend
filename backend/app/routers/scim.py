from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.middleware.entitlements import resolve_entitlements
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)
router = APIRouter(prefix="/scim/v2", tags=["scim"])

SCIM_SCHEMAS = {
    "user": "urn:ietf:params:scim:schemas:core:2.0:User",
    "group": "urn:ietf:params:scim:schemas:core:2.0:Group",
    "list": "urn:ietf:params:scim:api:messages:2.0:ListResponse",
    "patch": "urn:ietf:params:scim:api:messages:2.0:PatchOp",
    "error": "urn:ietf:params:scim:api:messages:2.0:Error",
}


class SCIMName(BaseModel):
    givenName: str | None = None
    familyName: str | None = None
    formatted: str | None = None


class SCIMEmail(BaseModel):
    value: EmailStr
    type: str = "work"
    primary: bool = True


class SCIMUser(BaseModel):
    schemas: list[str] = Field(default_factory=lambda: [SCIM_SCHEMAS["user"]])
    id: str | None = None
    externalId: str | None = None
    userName: EmailStr
    name: SCIMName | None = None
    emails: list[SCIMEmail] | None = None
    displayName: str | None = None
    active: bool = True
    groups: list[dict[str, str]] | None = None
    meta: dict[str, Any] | None = None


class SCIMGroup(BaseModel):
    schemas: list[str] = Field(default_factory=lambda: [SCIM_SCHEMAS["group"]])
    id: str | None = None
    externalId: str | None = None
    displayName: str
    members: list[dict[str, str]] | None = None
    meta: dict[str, Any] | None = None


class SCIMListResponse(BaseModel):
    schemas: list[str] = Field(default_factory=lambda: [SCIM_SCHEMAS["list"]])
    totalResults: int
    startIndex: int = 1
    itemsPerPage: int
    Resources: list[dict[str, Any]]


class SCIMPatchOp(BaseModel):
    schemas: list[str] = Field(default_factory=lambda: [SCIM_SCHEMAS["patch"]])
    Operations: list[dict[str, Any]]


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _build_meta(resource_type: str, resource_id: str, created: str | None, modified: str | None) -> dict[str, Any]:
    created_value = created or datetime.now(timezone.utc).isoformat()
    modified_value = modified or created_value
    return {
        "resourceType": resource_type,
        "created": created_value,
        "lastModified": modified_value,
        "location": f"/scim/v2/{resource_type}s/{resource_id}",
    }


def _assert_scim_feature(settings: Settings, org_id: str) -> None:
    entitlements = resolve_entitlements(settings, org_id)
    features = entitlements.get("features") or {}
    if not bool(features.get("sso_saml")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SCIM is available on Command tier only")


async def verify_scim_token(
    authorization: Annotated[str, Header()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    token = authorization[7:]
    client = get_supabase_client(settings)
    result = (
        client.table("scim_tokens")
        .select("id,org_id,is_active,expires_at")
        .eq("token_hash", _hash_token(token))
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    token_data = dict(result.data[0])
    expires_at = token_data.get("expires_at")
    if expires_at:
        try:
            expires_dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if expires_dt < datetime.now(timezone.utc):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    client.table("scim_tokens").update({"last_used_at": datetime.now(timezone.utc).isoformat()}).eq(
        "id", token_data["id"]
    ).execute()

    org_id = str(token_data["org_id"])
    _assert_scim_feature(settings, org_id)
    return {"org_id": org_id}


def _compose_full_name(user: SCIMUser) -> str | None:
    if user.displayName:
        return user.displayName.strip() or None
    if user.name:
        parts = [user.name.givenName or "", user.name.familyName or ""]
        full_name = " ".join(part.strip() for part in parts if part and part.strip())
        return full_name or None
    return None


def _user_to_scim(user: dict[str, Any], groups: list[dict[str, str]] | None = None) -> dict[str, Any]:
    full_name = str(user.get("full_name") or "")
    name_parts = full_name.split(" ", 1) if full_name else ["", ""]
    created = user.get("created_at")
    updated = user.get("updated_at")
    return {
        "schemas": [SCIM_SCHEMAS["user"]],
        "id": str(user["id"]),
        "externalId": user.get("external_id"),
        "userName": user["email"],
        "name": {
            "givenName": name_parts[0] if name_parts else "",
            "familyName": name_parts[1] if len(name_parts) > 1 else "",
            "formatted": full_name,
        },
        "displayName": full_name or None,
        "emails": [{"value": user["email"], "type": "work", "primary": True}],
        "active": bool(user.get("is_active", user.get("status") == "active")),
        "groups": groups or [],
        "meta": _build_meta("User", str(user["id"]), str(created) if created else None, str(updated) if updated else None),
    }


def _group_to_scim(group: dict[str, Any], members: list[dict[str, str]] | None = None) -> dict[str, Any]:
    created = group.get("created_at")
    updated = group.get("updated_at")
    return {
        "schemas": [SCIM_SCHEMAS["group"]],
        "id": str(group["id"]),
        "externalId": group.get("external_id"),
        "displayName": group.get("display_name") or "",
        "members": members or [],
        "meta": _build_meta("Group", str(group["id"]), str(created) if created else None, str(updated) if updated else None),
    }


def _get_group_members(client, group_id: str) -> list[dict[str, str]]:
    result = (
        client.table("scim_group_memberships")
        .select("user_id")
        .eq("group_id", group_id)
        .execute()
    )
    return [{"value": str(row["user_id"]), "$ref": f"/scim/v2/Users/{row['user_id']}"} for row in (result.data or [])]


@router.get("/Users", response_model=SCIMListResponse)
async def list_users(
    auth: Annotated[dict[str, Any], Depends(verify_scim_token)],
    startIndex: int = Query(1, ge=1),
    count: int = Query(100, ge=1, le=1000),
    filter: str | None = Query(None),
    settings: Settings = Depends(get_settings),
) -> SCIMListResponse:
    client = get_supabase_client(settings)
    org_id = auth["org_id"]

    query = client.table("users").select("id,email,full_name,is_active,status,created_at,updated_at,external_id", count="exact").eq(
        "org_id", org_id
    )
    if filter and "userName eq" in filter:
        match = re.search(r'userName eq "([^"]+)"', filter)
        if match:
            query = query.eq("email", match.group(1))

    offset = startIndex - 1
    result = query.range(offset, offset + count - 1).execute()
    users = [_user_to_scim(dict(user)) for user in (result.data or [])]
    return SCIMListResponse(
        totalResults=result.count or 0,
        startIndex=startIndex,
        itemsPerPage=len(users),
        Resources=users,
    )


@router.get("/Users/{user_id}", response_model=SCIMUser)
async def get_user(
    user_id: str,
    auth: Annotated[dict[str, Any], Depends(verify_scim_token)],
    settings: Settings = Depends(get_settings),
) -> SCIMUser:
    client = get_supabase_client(settings)
    result = (
        client.table("users")
        .select("*")
        .eq("id", user_id)
        .eq("org_id", auth["org_id"])
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return SCIMUser.model_validate(_user_to_scim(dict(result.data[0])))


@router.post("/Users", status_code=status.HTTP_201_CREATED, response_model=SCIMUser)
async def create_user(
    user: SCIMUser,
    auth: Annotated[dict[str, Any], Depends(verify_scim_token)],
    settings: Settings = Depends(get_settings),
) -> SCIMUser:
    client = get_supabase_client(settings)
    org_id = auth["org_id"]
    existing = client.table("users").select("id").eq("email", str(user.userName)).eq("org_id", org_id).limit(1).execute()
    if existing.data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": str(uuid4()),
        "org_id": org_id,
        "email": str(user.userName),
        "full_name": _compose_full_name(user),
        "external_id": user.externalId,
        "is_active": bool(user.active),
        "status": "active" if user.active else "disabled",
        "provisioned_via": "scim",
        "updated_at": now,
    }
    result = client.table("users").insert(row).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create user")
    created = dict(result.data[0])
    logger.info("scim_user_created user_id=%s org_id=%s", created["id"], org_id)
    return SCIMUser.model_validate(_user_to_scim(created))


@router.put("/Users/{user_id}", response_model=SCIMUser)
async def replace_user(
    user_id: str,
    user: SCIMUser,
    auth: Annotated[dict[str, Any], Depends(verify_scim_token)],
    settings: Settings = Depends(get_settings),
) -> SCIMUser:
    client = get_supabase_client(settings)
    org_id = auth["org_id"]
    existing = client.table("users").select("id").eq("id", user_id).eq("org_id", org_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="User not found")
    payload = {
        "email": str(user.userName),
        "full_name": _compose_full_name(user),
        "external_id": user.externalId,
        "is_active": bool(user.active),
        "status": "active" if user.active else "disabled",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = client.table("users").update(payload).eq("id", user_id).eq("org_id", org_id).execute()
    return SCIMUser.model_validate(_user_to_scim(dict(result.data[0])))


@router.patch("/Users/{user_id}", response_model=SCIMUser)
async def patch_user(
    user_id: str,
    patch: SCIMPatchOp,
    auth: Annotated[dict[str, Any], Depends(verify_scim_token)],
    settings: Settings = Depends(get_settings),
) -> SCIMUser:
    client = get_supabase_client(settings)
    org_id = auth["org_id"]
    existing = (
        client.table("users")
        .select("*")
        .eq("id", user_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="User not found")
    user_data = dict(existing.data[0])
    for op in patch.Operations:
        operation = str(op.get("op") or "").lower()
        path = str(op.get("path") or "")
        value = op.get("value")
        if operation != "replace":
            continue
        if path == "active":
            user_data["is_active"] = bool(value)
            user_data["status"] = "active" if bool(value) else "disabled"
        elif path == "userName":
            user_data["email"] = str(value)
        elif path in {"displayName", "name.formatted"}:
            user_data["full_name"] = str(value)
        elif path == "externalId":
            user_data["external_id"] = str(value) if value is not None else None
    user_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = client.table("users").update(user_data).eq("id", user_id).eq("org_id", org_id).execute()
    return SCIMUser.model_validate(_user_to_scim(dict(result.data[0])))


@router.delete("/Users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    auth: Annotated[dict[str, Any], Depends(verify_scim_token)],
    settings: Settings = Depends(get_settings),
) -> Response:
    client = get_supabase_client(settings)
    org_id = auth["org_id"]
    result = (
        client.table("users")
        .update({"is_active": False, "status": "disabled", "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", user_id)
        .eq("org_id", org_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/Groups", response_model=SCIMListResponse)
async def list_groups(
    auth: Annotated[dict[str, Any], Depends(verify_scim_token)],
    startIndex: int = Query(1, ge=1),
    count: int = Query(100, ge=1, le=1000),
    settings: Settings = Depends(get_settings),
) -> SCIMListResponse:
    client = get_supabase_client(settings)
    org_id = auth["org_id"]
    offset = startIndex - 1
    result = (
        client.table("scim_groups")
        .select("*", count="exact")
        .eq("org_id", org_id)
        .range(offset, offset + count - 1)
        .execute()
    )
    groups = []
    for group in result.data or []:
        members = _get_group_members(client, str(group["id"]))
        groups.append(_group_to_scim(dict(group), members=members))
    return SCIMListResponse(
        totalResults=result.count or 0,
        startIndex=startIndex,
        itemsPerPage=len(groups),
        Resources=groups,
    )


@router.get("/Groups/{group_id}", response_model=SCIMGroup)
async def get_group(
    group_id: str,
    auth: Annotated[dict[str, Any], Depends(verify_scim_token)],
    settings: Settings = Depends(get_settings),
) -> SCIMGroup:
    client = get_supabase_client(settings)
    result = (
        client.table("scim_groups")
        .select("*")
        .eq("id", group_id)
        .eq("org_id", auth["org_id"])
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Group not found")
    members = _get_group_members(client, group_id)
    return SCIMGroup.model_validate(_group_to_scim(dict(result.data[0]), members=members))


@router.post("/Groups", status_code=status.HTTP_201_CREATED, response_model=SCIMGroup)
async def create_group(
    group: SCIMGroup,
    auth: Annotated[dict[str, Any], Depends(verify_scim_token)],
    settings: Settings = Depends(get_settings),
) -> SCIMGroup:
    client = get_supabase_client(settings)
    org_id = auth["org_id"]
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": str(uuid4()),
        "org_id": org_id,
        "external_id": group.externalId,
        "display_name": group.displayName,
        "created_at": now,
        "updated_at": now,
    }
    result = client.table("scim_groups").insert(row).execute()
    if group.members:
        memberships = [{"group_id": row["id"], "user_id": member["value"], "created_at": now} for member in group.members]
        if memberships:
            client.table("scim_group_memberships").upsert(memberships, on_conflict="group_id,user_id").execute()
    members = _get_group_members(client, row["id"])
    return SCIMGroup.model_validate(_group_to_scim(dict(result.data[0]), members=members))


@router.put("/Groups/{group_id}", response_model=SCIMGroup)
async def replace_group(
    group_id: str,
    group: SCIMGroup,
    auth: Annotated[dict[str, Any], Depends(verify_scim_token)],
    settings: Settings = Depends(get_settings),
) -> SCIMGroup:
    client = get_supabase_client(settings)
    org_id = auth["org_id"]
    existing = client.table("scim_groups").select("id").eq("id", group_id).eq("org_id", org_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Group not found")
    payload = {
        "display_name": group.displayName,
        "external_id": group.externalId,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    updated = client.table("scim_groups").update(payload).eq("id", group_id).eq("org_id", org_id).execute()
    client.table("scim_group_memberships").delete().eq("group_id", group_id).execute()
    if group.members:
        memberships = [{"group_id": group_id, "user_id": member["value"]} for member in group.members]
        client.table("scim_group_memberships").insert(memberships).execute()
    members = _get_group_members(client, group_id)
    return SCIMGroup.model_validate(_group_to_scim(dict(updated.data[0]), members=members))


@router.patch("/Groups/{group_id}", response_model=SCIMGroup)
async def patch_group(
    group_id: str,
    patch: SCIMPatchOp,
    auth: Annotated[dict[str, Any], Depends(verify_scim_token)],
    settings: Settings = Depends(get_settings),
) -> SCIMGroup:
    client = get_supabase_client(settings)
    org_id = auth["org_id"]
    existing = client.table("scim_groups").select("*").eq("id", group_id).eq("org_id", org_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Group not found")
    for op in patch.Operations:
        operation = str(op.get("op") or "").lower()
        path = str(op.get("path") or "")
        value = op.get("value")
        if path == "displayName" and operation == "replace":
            client.table("scim_groups").update(
                {"display_name": str(value), "updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", group_id).eq("org_id", org_id).execute()
        if path.startswith("members") or path == "members":
            members = value if isinstance(value, list) else [value]
            if operation == "add":
                rows = [{"group_id": group_id, "user_id": member["value"]} for member in members]
                client.table("scim_group_memberships").upsert(rows, on_conflict="group_id,user_id").execute()
            elif operation == "remove":
                for member in members:
                    client.table("scim_group_memberships").delete().eq("group_id", group_id).eq(
                        "user_id", member["value"]
                    ).execute()
            elif operation == "replace":
                client.table("scim_group_memberships").delete().eq("group_id", group_id).execute()
                rows = [{"group_id": group_id, "user_id": member["value"]} for member in members]
                if rows:
                    client.table("scim_group_memberships").insert(rows).execute()
    refreshed = client.table("scim_groups").select("*").eq("id", group_id).eq("org_id", org_id).limit(1).execute()
    members = _get_group_members(client, group_id)
    return SCIMGroup.model_validate(_group_to_scim(dict(refreshed.data[0]), members=members))


@router.delete("/Groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    auth: Annotated[dict[str, Any], Depends(verify_scim_token)],
    settings: Settings = Depends(get_settings),
) -> Response:
    client = get_supabase_client(settings)
    org_id = auth["org_id"]
    client.table("scim_group_memberships").delete().eq("group_id", group_id).execute()
    result = client.table("scim_groups").delete().eq("id", group_id).eq("org_id", org_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Group not found")
    logger.info("scim_group_deleted group_id=%s org_id=%s", group_id, org_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

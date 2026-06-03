"""Admin API for agent tool permissions (STA-11)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.agent_tool_permissions import (
    delete_agent_tool_permission,
    list_agent_tool_permissions,
    upsert_agent_tool_permission,
)
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/agents", tags=["agent-tool-permissions"])


class ToolPermissionGrant(BaseModel):
    connector_id: str | None = Field(default=None, alias="connectorId")
    connector_type: str | None = Field(default=None, alias="connectorType")
    scopes: list[str] = Field(default_factory=list)
    expires_at: str | None = Field(default=None, alias="expiresAt")

    model_config = {"populate_by_name": True}


class ToolPermissionResponse(BaseModel):
    id: str
    agent_id: str = Field(alias="agentId")
    connector_id: str | None = Field(default=None, alias="connectorId")
    connector_type: str | None = Field(default=None, alias="connectorType")
    scopes: list[str]
    granted_by: str | None = Field(default=None, alias="grantedBy")
    granted_at: str | None = Field(default=None, alias="grantedAt")
    expires_at: str | None = Field(default=None, alias="expiresAt")

    model_config = {"populate_by_name": True}


def _to_response(row: dict) -> ToolPermissionResponse:
    return ToolPermissionResponse(
        id=str(row["id"]),
        agent_id=str(row["agent_id"]),
        connector_id=str(row["connector_id"]) if row.get("connector_id") else None,
        connector_type=row.get("connector_type"),
        scopes=list(row.get("scopes") or []),
        granted_by=str(row["granted_by"]) if row.get("granted_by") else None,
        granted_at=row.get("granted_at"),
        expires_at=row.get("expires_at"),
    )


@router.get("/{agent_id}/tool-permissions", response_model=list[ToolPermissionResponse])
async def list_tool_permissions(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ToolPermissionResponse]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    rows = list_agent_tool_permissions(client, org_id, str(agent_id))
    return [_to_response(r) for r in rows]


@router.put("/{agent_id}/tool-permissions", response_model=ToolPermissionResponse)
async def grant_tool_permission(
    agent_id: UUID,
    body: ToolPermissionGrant,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ToolPermissionResponse:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context required")
    if not body.connector_id and not body.connector_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="connectorId or connectorType is required",
        )
    if not body.scopes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scopes must not be empty")

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = upsert_agent_tool_permission(
        client,
        org_id,
        str(agent_id),
        connector_id=body.connector_id,
        connector_type=body.connector_type,
        scopes=body.scopes,
        granted_by=current_user["user_id"],
        expires_at=body.expires_at,
    )
    write_audit_event(
        client,
        org_id,
        current_user["user_id"],
        action="agent.tool_permission.granted",
        resource_type="agent",
        resource_id=str(agent_id),
        metadata={
            "connector_id": body.connector_id,
            "connector_type": body.connector_type,
            "scope_count": len(body.scopes),
        },
    )
    return _to_response(row)


@router.delete("/{agent_id}/tool-permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_tool_permission(
    agent_id: UUID,
    permission_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    delete_agent_tool_permission(client, org_id, str(permission_id))
    write_audit_event(
        client,
        org_id,
        current_user["user_id"],
        action="agent.tool_permission.revoked",
        resource_type="agent",
        resource_id=str(agent_id),
        metadata={"permission_id": str(permission_id)},
    )

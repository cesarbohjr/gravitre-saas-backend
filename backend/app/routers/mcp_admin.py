"""Admin API for MCP server and tool management."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.mcp_client_service import (
    MCPClientService,
    encrypt_auth_config,
    get_mcp_client_service,
)
from app.workflows.repository import get_supabase_client

router = APIRouter(prefix="/api/admin/mcp", tags=["mcp-admin"])


class MCPServerCreateRequest(BaseModel):
    server_name: str = Field(..., min_length=1, alias="serverName")
    server_url: str = Field(..., min_length=1, alias="serverUrl")
    transport: str = Field(default="stdio")
    auth_type: str = Field(default="none", alias="authType")
    auth_config: dict[str, Any] = Field(default_factory=dict, alias="authConfig")
    enabled: bool = True

    model_config = {"populate_by_name": True}


class MCPToolPatchRequest(BaseModel):
    enabled: bool


class MCPServerPatchRequest(BaseModel):
    enabled: bool


@router.get("/servers")
async def list_mcp_servers(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    rows = (
        client.table("mcp_servers")
        .select("id, server_name, server_url, transport, auth_type, enabled, verified_by_gravitre, source_capability_package_id, activation_state, created_at")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    return {"servers": rows}


@router.post("/servers")
async def create_mcp_server(
    body: MCPServerCreateRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user, _org = admin
    user_id = str(user.get("user_id") or user.get("id") or "")
    client = get_supabase_client(settings)
    auth_config = body.auth_config
    if body.auth_type != "none" and auth_config:
        key = getattr(settings, "connector_secrets_encryption_key", None) or ""
        if not key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CONNECTOR_SECRETS_ENCRYPTION_KEY required to store MCP auth",
            )
        auth_config = encrypt_auth_config(auth_config, str(key))
    row = {
        "org_id": org_id,
        "server_name": body.server_name.strip(),
        "server_url": body.server_url.strip(),
        "transport": body.transport,
        "auth_type": body.auth_type,
        "auth_config": auth_config,
        "enabled": body.enabled,
        "created_by": user_id or None,
    }
    inserted = client.table("mcp_servers").insert(row).execute()
    return {"server": inserted.data[0] if inserted.data else row}


@router.delete("/servers/{server_id}")
async def delete_mcp_server(
    server_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    client.table("mcp_servers").delete().eq("id", server_id).eq("org_id", org_id).execute()
    return {"deleted": True, "serverId": server_id}


@router.patch("/servers/{server_id}")
async def patch_mcp_server(
    server_id: str,
    body: MCPServerPatchRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    rows = (
        client.table("mcp_servers")
        .select("id,source_capability_package_id,activation_state")
        .eq("id", server_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found")
    current = rows[0]
    if body.enabled and current.get("source_capability_package_id"):
        tool_rows = (
            client.table("mcp_tools")
            .select("id")
            .eq("org_id", org_id)
            .eq("server_id", server_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not tool_rows:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Discover and review MCP tools before enabling this capability server",
            )
    patch: dict[str, Any] = {"enabled": bool(body.enabled)}
    if current.get("source_capability_package_id"):
        patch["activation_state"] = "configured" if body.enabled else "disabled"
    updated = (
        client.table("mcp_servers")
        .update(patch)
        .eq("id", server_id)
        .eq("org_id", org_id)
        .execute()
    )
    return {"server": updated.data[0] if updated.data else {**current, **patch}}


@router.post("/servers/{server_id}/discover")
async def discover_mcp_tools(
    server_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    server_rows = (
        client.table("mcp_servers")
        .select("id,enabled,source_capability_package_id,activation_state")
        .eq("id", server_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not server_rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found")
    server = server_rows[0]
    imported_pending = bool(server.get("source_capability_package_id")) and (
        not bool(server.get("enabled"))
        or str(server.get("activation_state") or "") in {"pending_review", "disabled"}
    )
    service = get_mcp_client_service(settings)
    try:
        tools = await service.discover_tools(
            server_id,
            org_id,
            allow_disabled_server=imported_pending,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"tools": tools, "count": len(tools)}


@router.get("/tools")
async def list_mcp_tools(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    rows = (
        client.table("mcp_tools")
        .select(
            "id, server_id, tool_name, tool_description, capability_tier, "
            "requires_approval, enabled, risk_level, created_at"
        )
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    return {"tools": rows}


@router.patch("/tools/{tool_id}")
async def patch_mcp_tool(
    tool_id: str,
    body: MCPToolPatchRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    if body.enabled:
        tool_rows = (
            client.table("mcp_tools")
            .select("id,server_id")
            .eq("id", tool_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not tool_rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
        server_rows = (
            client.table("mcp_servers")
            .select("id,enabled,activation_state")
            .eq("id", str(tool_rows[0].get("server_id") or ""))
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        server = server_rows[0] if server_rows else {}
        if not bool(server.get("enabled")) or str(server.get("activation_state") or "configured") in {"pending_review", "disabled"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Enable and approve the MCP server before enabling its tools",
            )
    updated = (
        client.table("mcp_tools")
        .update({"enabled": body.enabled})
        .eq("id", tool_id)
        .eq("org_id", org_id)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
    return {"tool": updated.data[0]}

"""MCP client integration — two-tier safety (read direct, write requires approval)."""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.connectors.crypto import decrypt_secret, encrypt_secret
from app.core.logging import get_logger
from app.services.approval_record_service import create_contract_approval
from app.workflows.audit import write_audit_event
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

_WRITE_KEYWORDS = frozenset(
    {"create", "update", "delete", "send", "write", "modify", "post", "put", "patch"}
)

_ENCRYPTED_AUTH_KEYS = frozenset({"api_key", "token", "bearer_token", "access_token", "secret"})


def classify_mcp_tool_capability(tool_name: str, tool_description: str | None = None) -> str:
    """Conservative keyword fallback when MCP annotations are absent (discovery only)."""
    haystack = f"{tool_name} {tool_description or ''}".lower()
    tokens = set(re.split(r"[^a-z0-9]+", haystack))
    if tokens & _WRITE_KEYWORDS:
        return "write"
    for keyword in _WRITE_KEYWORDS:
        if keyword in haystack:
            return "write"
    return "read"


def resolve_mcp_tool_authority(
    tool_name: str,
    tool_description: str | None = None,
    input_schema: dict[str, Any] | None = None,
) -> tuple[str, bool, bool | None, bool | None]:
    """Return (capability_tier, requires_approval, read_only_hint, destructive_hint).

    Uses MCP annotation hints when present; keyword classifier is fallback only.
    """
    from app.services.catalog_write_authority import (
        mcp_hints_from_schema,
        mcp_tool_requires_write_approval,
    )

    read_only, destructive = mcp_hints_from_schema(input_schema)
    if read_only is True:
        return "read", False, read_only, destructive
    if destructive is True:
        return "write", True, read_only, destructive
    capability = classify_mcp_tool_capability(tool_name, tool_description)
    requires = mcp_tool_requires_write_approval(capability_tier=capability)
    return capability, requires, read_only, destructive


def encrypt_auth_config(auth_config: dict[str, Any], encryption_key: str) -> dict[str, Any]:
    if not auth_config:
        return {}
    encrypted: dict[str, Any] = {}
    for key, value in auth_config.items():
        if key in _ENCRYPTED_AUTH_KEYS and value not in (None, ""):
            encrypted[key] = encrypt_secret(str(value), encryption_key)
        else:
            encrypted[key] = value
    encrypted["_encrypted"] = True
    return encrypted


def decrypt_auth_config(auth_config: dict[str, Any], encryption_key: str) -> dict[str, Any]:
    if not auth_config:
        return {}
    plain: dict[str, Any] = {}
    for key, value in auth_config.items():
        if key.startswith("_"):
            continue
        if key in _ENCRYPTED_AUTH_KEYS and isinstance(value, str) and value:
            try:
                plain[key] = decrypt_secret(value, encryption_key)
            except ValueError:
                plain[key] = value
        else:
            plain[key] = value
    return plain


def mcp_openai_tool_name(server_name: str, tool_name: str) -> str:
    safe_server = re.sub(r"[^a-z0-9_]+", "_", server_name.lower()).strip("_") or "server"
    safe_tool = re.sub(r"[^a-z0-9_]+", "_", tool_name.lower()).strip("_") or "tool"
    return f"mcp_{safe_server}_{safe_tool}"[:128]


class MCPClientService:
    """Org-scoped MCP tool discovery and execution with mandatory write approval."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _encryption_key(self) -> str:
        key = getattr(self.settings, "connector_secrets_encryption_key", None) or ""
        if not key:
            raise ValueError("CONNECTOR_SECRETS_ENCRYPTION_KEY is required for MCP server auth")
        return str(key)

    async def discover_tools(self, server_id: str, org_id: str) -> list[dict[str, Any]]:
        server = await self._load_server(server_id, org_id)
        remote_tools = await self._list_remote_tools(server)
        client = self._client()
        upserted: list[dict[str, Any]] = []
        for remote in remote_tools:
            name = str(remote.get("name") or "").strip()
            if not name:
                continue
            description = str(remote.get("description") or "")
            schema = remote.get("inputSchema") or remote.get("input_schema") or {}
            if not isinstance(schema, dict):
                schema = {}
            capability, requires_approval, read_only_hint, destructive_hint = (
                resolve_mcp_tool_authority(name, description, schema)
            )
            existing = (
                client.table("mcp_tools")
                .select("id")
                .eq("org_id", org_id)
                .eq("server_id", server_id)
                .eq("tool_name", name)
                .limit(1)
                .execute()
                .data
                or []
            )
            row = {
                "server_id": server_id,
                "org_id": org_id,
                "tool_name": name,
                "tool_description": description,
                "input_schema": schema,
                "capability_tier": capability,
                "enabled": True,
                "risk_level": "high" if capability == "write" else "low",
            }
            if existing:
                updated = (
                    client.table("mcp_tools")
                    .update(row)
                    .eq("id", existing[0]["id"])
                    .eq("org_id", org_id)
                    .execute()
                )
                upserted.append(updated.data[0] if updated.data else row)
            else:
                inserted = client.table("mcp_tools").insert(row).execute()
                upserted.append(inserted.data[0] if inserted.data else row)
        server_name = str(server.get("server_name") or server_id)
        from app.services.mcp_catalog_sync import sync_mcp_server_to_catalog

        sync_mcp_server_to_catalog(
            server_name=server_name,
            server_id=server_id,
            tools=upserted,
        )
        from app.connectors.action_catalog.extensions import register_action_schemas

        mcp_schemas: dict[str, dict] = {}
        for row in upserted:
            schema = row.get("input_schema") if isinstance(row.get("input_schema"), dict) else {}
            if schema:
                openai_name = mcp_openai_tool_name(server_name, str(row.get("tool_name") or ""))
                mcp_schemas[openai_name] = schema
        if mcp_schemas:
            register_action_schemas(mcp_schemas)
        return upserted

    async def execute_tool(
        self,
        tool_id: str,
        org_id: str,
        input_data: dict[str, Any],
        *,
        agent_id: str | None = None,
        workflow_run_id: str | None = None,
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        tool = await self._load_tool(tool_id, org_id)
        if not tool.get("enabled", True):
            return {"status": "failed", "error": "MCP tool is disabled"}

        from app.services.catalog_write_authority import (
            mcp_hints_from_schema,
            mcp_tool_requires_write_approval,
        )

        schema = tool.get("input_schema") if isinstance(tool.get("input_schema"), dict) else {}
        read_only_hint, destructive_hint = mcp_hints_from_schema(schema)
        requires_write = mcp_tool_requires_write_approval(
            capability_tier=str(tool.get("capability_tier") or "") or None,
            requires_approval=bool(tool.get("requires_approval")),
            read_only_hint=read_only_hint,
            destructive_hint=destructive_hint,
        )
        if requires_write:
            if not approval_id:
                pending = await self._create_pending_execution(
                    tool_id=tool_id,
                    org_id=org_id,
                    agent_id=agent_id,
                    workflow_run_id=workflow_run_id,
                    input_data=input_data,
                    tool=tool,
                )
                return {
                    "status": "pending_approval",
                    "execution_id": pending.get("execution_id"),
                    "approval_id": pending.get("approval_id"),
                    "message": (
                        "This write action requires approval. Check the Approvals queue to proceed."
                    ),
                }
            await self._verify_approval(approval_id, tool_id, org_id)

        server = await self._load_server(str(tool["server_id"]), org_id)
        started = time.perf_counter()
        try:
            result = await self._call_mcp_server(server, str(tool["tool_name"]), input_data)
            latency_ms = int((time.perf_counter() - started) * 1000)
            await self._log_execution(
                tool_id=tool_id,
                org_id=org_id,
                agent_id=agent_id,
                workflow_run_id=workflow_run_id,
                input_data=input_data,
                output=result,
                status="completed",
                approval_id=approval_id,
                latency_ms=latency_ms,
                capability_tier=str(tool.get("capability_tier") or ""),
            )
            await self._audit_execution(org_id, tool, approval_id)
            return {"status": "completed", "result": result, "latency_ms": latency_ms}
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.perf_counter() - started) * 1000)
            await self._log_execution(
                tool_id=tool_id,
                org_id=org_id,
                agent_id=agent_id,
                workflow_run_id=workflow_run_id,
                input_data=input_data,
                output=None,
                status="failed",
                approval_id=approval_id,
                latency_ms=latency_ms,
                error=str(exc),
                capability_tier=str(tool.get("capability_tier") or ""),
            )
            return {"status": "failed", "error": str(exc), "latency_ms": latency_ms}

    async def get_enabled_tools_for_org(self, org_id: str) -> list[dict[str, Any]]:
        client = self._client()
        rows = (
            client.table("mcp_tools")
            .select("*, mcp_servers(server_name)")
            .eq("org_id", org_id)
            .eq("enabled", True)
            .execute()
            .data
            or []
        )
        tools: list[dict[str, Any]] = []
        for row in rows:
            server_name = ""
            nested = row.get("mcp_servers")
            if isinstance(nested, dict):
                server_name = str(nested.get("server_name") or "")
            from app.services.catalog_write_authority import (
                mcp_hints_from_schema,
                mcp_tool_requires_write_approval,
            )

            openai_name = mcp_openai_tool_name(server_name, str(row.get("tool_name") or ""))
            schema = row.get("input_schema") if isinstance(row.get("input_schema"), dict) else {}
            capability = str(row.get("capability_tier") or "read")
            read_only_hint, destructive_hint = mcp_hints_from_schema(schema)
            requires_approval = mcp_tool_requires_write_approval(
                capability_tier=capability,
                requires_approval=bool(row.get("requires_approval")),
                read_only_hint=read_only_hint,
                destructive_hint=destructive_hint,
            )
            tools.append(
                {
                    "name": openai_name,
                    "mcp_tool_id": str(row["id"]),
                    "integration": "mcp",
                    "capability_tier": capability,
                    "requires_approval": requires_approval,
                    "read_only_hint": read_only_hint,
                    "destructive_hint": destructive_hint,
                    "description": row.get("tool_description") or f"MCP tool {row.get('tool_name')}",
                    "parameters": schema.get("properties") or schema,
                    "input_schema": schema,
                }
            )
        return tools

    async def _load_server(self, server_id: str, org_id: str) -> dict[str, Any]:
        client = self._client()
        rows = (
            client.table("mcp_servers")
            .select("*")
            .eq("id", server_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            raise ValueError("MCP server not found for org")
        server = dict(rows[0])
        if not server.get("enabled", True):
            raise ValueError("MCP server is disabled")
        auth_config = server.get("auth_config") if isinstance(server.get("auth_config"), dict) else {}
        if auth_config.get("_encrypted"):
            server["auth_config"] = decrypt_auth_config(auth_config, self._encryption_key())
        return server

    async def _load_tool(self, tool_id: str, org_id: str) -> dict[str, Any]:
        client = self._client()
        rows = (
            client.table("mcp_tools")
            .select("*")
            .eq("id", tool_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            raise ValueError("MCP tool not found for org")
        return dict(rows[0])

    async def _verify_approval(self, approval_id: str, tool_id: str, org_id: str) -> None:
        client = self._client()
        rows = (
            client.table("approvals")
            .select("id, status, context")
            .eq("id", approval_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            raise ValueError("Approval not found")
        row = rows[0]
        if str(row.get("status") or "") != "approved":
            raise ValueError("Approval is not approved")
        context = row.get("context") if isinstance(row.get("context"), dict) else {}
        if str(context.get("mcp_tool_id") or "") != str(tool_id):
            raise ValueError("Approval does not match MCP tool")

    async def _create_pending_execution(
        self,
        *,
        tool_id: str,
        org_id: str,
        agent_id: str | None,
        workflow_run_id: str | None,
        input_data: dict[str, Any],
        tool: dict[str, Any],
    ) -> dict[str, Any]:
        client = self._client()
        inserted = (
            client.table("mcp_tool_executions")
            .insert(
                {
                    "org_id": org_id,
                    "tool_id": tool_id,
                    "agent_id": agent_id,
                    "workflow_run_id": workflow_run_id,
                    "input": input_data,
                    "status": "pending_approval",
                }
            )
            .execute()
        )
        execution = inserted.data[0] if inserted.data else {}
        execution_id = str(execution.get("id") or "")
        approval = create_contract_approval(
            client,
            org_id=org_id,
            title=f"Approve MCP write: {tool.get('tool_name')}",
            description="MCP write tool execution requires human approval.",
            approval_type="mcp_tool",
            priority="high",
            status="pending",
            context={
                "mcp_tool_id": tool_id,
                "mcp_execution_id": execution_id,
                "tool_name": tool.get("tool_name"),
            },
            parameters=input_data,
        )
        approval_id = str((approval or {}).get("id") or "")
        if approval_id:
            client.table("mcp_tool_executions").update({"approval_id": approval_id}).eq(
                "id", execution_id
            ).eq("org_id", org_id).execute()
        return {"execution_id": execution_id, "approval_id": approval_id}

    async def _log_execution(
        self,
        *,
        tool_id: str,
        org_id: str,
        agent_id: str | None,
        workflow_run_id: str | None,
        input_data: dict[str, Any],
        output: dict[str, Any] | None,
        status: str,
        approval_id: str | None,
        latency_ms: int | None,
        error: str | None = None,
        capability_tier: str = "",
    ) -> None:
        client = self._client()
        client.table("mcp_tool_executions").insert(
            {
                "org_id": org_id,
                "tool_id": tool_id,
                "agent_id": agent_id,
                "workflow_run_id": workflow_run_id,
                "input": input_data,
                "output": output,
                "status": status,
                "approval_id": approval_id,
                "latency_ms": latency_ms,
                "error": error,
            }
        ).execute()
        self._mirror_execution_to_clickhouse(
            org_id=org_id,
            tool_id=tool_id,
            capability_tier=capability_tier,
            status=status,
            latency_ms=latency_ms,
        )

    def _mirror_execution_to_clickhouse(
        self,
        *,
        org_id: str,
        tool_id: str,
        capability_tier: str,
        status: str,
        latency_ms: int | None,
    ) -> None:
        try:
            from datetime import datetime, timezone

            from app.services.clickhouse_service import get_clickhouse_service

            ch_row = {
                "org_id": org_id,
                "tool_id": tool_id,
                "capability_tier": capability_tier,
                "status": status,
                "latency_ms": int(latency_ms or 0),
                "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
            }
            asyncio.create_task(
                get_clickhouse_service().insert_events("gravitre.mcp_executions", [ch_row])
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("clickhouse_mcp_execution_skipped error=%s", exc)

    async def _audit_execution(
        self,
        org_id: str,
        tool: dict[str, Any],
        approval_id: str | None,
    ) -> None:
        try:
            await asyncio.to_thread(
                write_audit_event,
                self._client(),
                org_id=org_id,
                action="mcp.tool.executed",
                resource_type="mcp_tool",
                resource_id=str(tool.get("id") or ""),
                details={
                    "tool_name": tool.get("tool_name"),
                    "capability_tier": tool.get("capability_tier"),
                    "approval_id": approval_id,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("mcp_audit_failed org=%s error=%s", org_id, exc)

    async def _list_remote_tools(self, server: dict[str, Any]) -> list[dict[str, Any]]:
        """List tools from MCP server; override in tests via patch."""
        transport = str(server.get("transport") or "stdio")
        if transport == "stdio":
            return await self._list_tools_stdio(server)
        if transport in {"sse", "http"}:
            return await self._list_tools_http(server)
        raise ValueError(f"Unsupported MCP transport: {transport}")

    async def _call_mcp_server(
        self,
        server: dict[str, Any],
        tool_name: str,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        transport = str(server.get("transport") or "stdio")
        if transport == "stdio":
            return await self._call_stdio(server, tool_name, input_data)
        if transport in {"sse", "http"}:
            return await self._call_http(server, tool_name, input_data)
        raise ValueError(f"Unsupported MCP transport: {transport}")

    async def _list_tools_stdio(self, server: dict[str, Any]) -> list[dict[str, Any]]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        command_line = str(server.get("server_url") or "").strip()
        if not command_line:
            return []
        parts = command_line.split()
        params = StdioServerParameters(command=parts[0], args=parts[1:])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                return [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema,
                    }
                    for tool in listed.tools
                ]

    async def _list_tools_http(self, server: dict[str, Any]) -> list[dict[str, Any]]:
        from mcp.client.sse import sse_client

        url = str(server.get("server_url") or "")
        headers = self._auth_headers(server)
        async with sse_client(url, headers=headers) as (read, write):
            from mcp import ClientSession

            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                return [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema,
                    }
                    for tool in listed.tools
                ]

    async def _call_stdio(
        self,
        server: dict[str, Any],
        tool_name: str,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        command_line = str(server.get("server_url") or "").strip()
        parts = command_line.split()
        params = StdioServerParameters(command=parts[0], args=parts[1:])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, input_data)
                return {"content": [block.model_dump() for block in result.content]}

    async def _call_http(
        self,
        server: dict[str, Any],
        tool_name: str,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        url = str(server.get("server_url") or "")
        headers = self._auth_headers(server)
        async with sse_client(url, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, input_data)
                return {"content": [block.model_dump() for block in result.content]}

    def _auth_headers(self, server: dict[str, Any]) -> dict[str, str]:
        auth_type = str(server.get("auth_type") or "none")
        auth_config = server.get("auth_config") if isinstance(server.get("auth_config"), dict) else {}
        if auth_type == "bearer":
            token = auth_config.get("bearer_token") or auth_config.get("token")
            if token:
                return {"Authorization": f"Bearer {token}"}
        if auth_type == "api_key":
            key = auth_config.get("api_key")
            header = str(auth_config.get("header") or "X-API-Key")
            if key:
                return {header: str(key)}
        return {}


_mcp_client_service: MCPClientService | None = None


def get_mcp_client_service(settings: Settings | None = None) -> MCPClientService:
    global _mcp_client_service
    if settings is not None:
        return MCPClientService(settings=settings)
    if _mcp_client_service is None:
        _mcp_client_service = MCPClientService()
    return _mcp_client_service

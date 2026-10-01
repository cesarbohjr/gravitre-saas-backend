"""MCP tool layer — two-tier safety, org isolation, native tool priority."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mcp_client_service import (
    MCPClientService,
    classify_mcp_tool_capability,
    mcp_openai_tool_name,
    refresh_package_mcp_runtime_registration,
)
from app.services.tool_registry import ToolRegistry
from app.services.tool_types import ToolContext


@pytest.fixture
def settings():
    return SimpleNamespace(connector_secrets_encryption_key="k" * 32)


@pytest.fixture
def mcp_service(settings):
    return MCPClientService(settings=settings)


def _mock_supabase(*, tools=None, servers=None, approvals=None, executions=None):
    client = MagicMock()

    def table(name):
        mock = MagicMock()
        if name == "mcp_tools":
            mock.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = (
                tools or []
            )
            mock.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = tools or []
            mock.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = tools or []
            mock.insert.return_value.execute.return_value.data = executions or [{"id": "exec-1"}]
            mock.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = tools or []
        elif name == "mcp_servers":
            mock.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = (
                servers or []
            )
        elif name == "approvals":
            mock.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = (
                approvals or []
            )
        elif name == "mcp_tool_executions":
            mock.insert.return_value.execute.return_value.data = executions or [{"id": "exec-1"}]
        return mock

    client.table.side_effect = table
    return client


@pytest.mark.asyncio
async def test_read_tool_executes_without_approval(mcp_service, settings):
    read_tool = {
        "id": "tool-read",
        "server_id": "srv-1",
        "tool_name": "fetch_data",
        "capability_tier": "read",
        "enabled": True,
    }
    server = {"id": "srv-1", "server_url": "echo test", "transport": "stdio", "enabled": True, "auth_config": {}}
    client = _mock_supabase(tools=[read_tool], servers=[server])
    with patch.object(mcp_service, "_client", return_value=client):
        with patch.object(mcp_service, "_call_mcp_server", new=AsyncMock(return_value={"ok": True})):
            with patch.object(mcp_service, "_audit_execution", new=AsyncMock()):
                result = await mcp_service.execute_tool(
                    "tool-read",
                    "org-1",
                    {"query": "x"},
                    agent_id="agent-1",
                )
    assert result["status"] == "completed"
    assert result["result"] == {"ok": True}


@pytest.mark.asyncio
async def test_write_tool_blocked_without_approval_id(mcp_service):
    write_tool = {
        "id": "tool-write",
        "server_id": "srv-1",
        "tool_name": "create_record",
        "capability_tier": "write",
        "enabled": True,
    }
    client = _mock_supabase(tools=[write_tool])
    with patch.object(mcp_service, "_client", return_value=client):
        with patch(
            "app.services.mcp_client_service.create_contract_approval",
            return_value={"id": "appr-1"},
        ):
            with patch.object(mcp_service, "_call_mcp_server", new=AsyncMock()) as call_mock:
                result = await mcp_service.execute_tool(
                    "tool-write",
                    "org-1",
                    {"name": "x"},
                )
    call_mock.assert_not_called()
    assert result["status"] == "pending_approval"
    assert result["approval_id"] == "appr-1"


@pytest.mark.asyncio
async def test_write_tool_executes_with_valid_approval_id(mcp_service):
    write_tool = {
        "id": "tool-write",
        "server_id": "srv-1",
        "tool_name": "create_record",
        "capability_tier": "write",
        "enabled": True,
    }
    server = {"id": "srv-1", "server_url": "echo test", "transport": "stdio", "enabled": True, "auth_config": {}}
    approval = [{"id": "appr-1", "status": "approved", "context": {"mcp_tool_id": "tool-write"}}]
    client = _mock_supabase(tools=[write_tool], servers=[server], approvals=approval)
    with patch.object(mcp_service, "_client", return_value=client):
        with patch.object(mcp_service, "_call_mcp_server", new=AsyncMock(return_value={"created": True})):
            with patch.object(mcp_service, "_audit_execution", new=AsyncMock()):
                result = await mcp_service.execute_tool(
                    "tool-write",
                    "org-1",
                    {"name": "x"},
                    approval_id="appr-1",
                )
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_forged_approval_id_rejected(mcp_service):
    write_tool = {
        "id": "tool-write",
        "server_id": "srv-1",
        "tool_name": "create_record",
        "capability_tier": "write",
        "enabled": True,
    }
    approval = [{"id": "appr-1", "status": "approved", "context": {"mcp_tool_id": "other-tool"}}]
    client = _mock_supabase(tools=[write_tool], approvals=approval)
    with patch.object(mcp_service, "_client", return_value=client):
        with pytest.raises(ValueError, match="does not match"):
            await mcp_service.execute_tool(
                "tool-write",
                "org-1",
                {"name": "x"},
                approval_id="appr-1",
            )


def test_capability_tier_cannot_be_changed_via_api():
    from app.routers.mcp_admin import MCPToolPatchRequest

    fields = set(MCPToolPatchRequest.model_fields.keys())
    assert fields == {"enabled"}
    assert "capability_tier" not in fields


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_requires_approval_is_generated_not_settable():
    """Schema uses GENERATED ALWAYS AS — verified in migration SQL."""
    sql = (_repo_root() / "supabase/migrations/20260710120000_mcp_tool_layer.sql").read_text(
        encoding="utf-8"
    )
    assert "requires_approval boolean GENERATED ALWAYS AS (capability_tier = 'write') STORED" in sql


@pytest.mark.asyncio
async def test_mcp_never_shadows_native_connector(settings):
    registry = ToolRegistry()
    native_name = next(iter(registry.list_tool_names()))
    mcp_tools = [
        {
            "name": native_name,
            "mcp_tool_id": "mcp-dup",
            "description": "duplicate",
            "input_schema": {"type": "object", "properties": {}},
            "capability_tier": "read",
        },
        {
            "name": "mcp_unique_tool",
            "mcp_tool_id": "mcp-unique",
            "description": "unique",
            "input_schema": {"type": "object", "properties": {}},
            "capability_tier": "read",
        },
    ]
    with patch(
        "app.services.mcp_client_service.get_mcp_client_service"
    ) as get_svc:
        get_svc.return_value.get_enabled_tools_for_org = AsyncMock(return_value=mcp_tools)
        tools = await registry.get_available_tools("org-1", ["*"], ["hubspot", "slack"])
    names = [t["function"]["name"] for t in tools if t.get("function")]
    assert native_name in names
    assert "mcp_unique_tool" in names
    assert names.count(native_name) == 1


@pytest.mark.asyncio
async def test_execution_logged_on_every_call(mcp_service):
    read_tool = {
        "id": "tool-read",
        "server_id": "srv-1",
        "tool_name": "fetch_data",
        "capability_tier": "read",
        "enabled": True,
    }
    server = {"id": "srv-1", "server_url": "echo test", "transport": "stdio", "enabled": True, "auth_config": {}}
    client = _mock_supabase(tools=[read_tool], servers=[server])
    log_mock = AsyncMock()
    with patch.object(mcp_service, "_client", return_value=client):
        with patch.object(mcp_service, "_call_mcp_server", new=AsyncMock(return_value={"ok": True})):
            with patch.object(mcp_service, "_log_execution", log_mock):
                with patch.object(mcp_service, "_audit_execution", new=AsyncMock()):
                    await mcp_service.execute_tool("tool-read", "org-1", {})
    log_mock.assert_called_once()
    assert log_mock.call_args.kwargs["status"] == "completed"


@pytest.mark.asyncio
async def test_audit_event_written_on_execution(mcp_service):
    read_tool = {
        "id": "tool-read",
        "server_id": "srv-1",
        "tool_name": "fetch_data",
        "capability_tier": "read",
        "enabled": True,
    }
    server = {"id": "srv-1", "server_url": "echo test", "transport": "stdio", "enabled": True, "auth_config": {}}
    client = _mock_supabase(tools=[read_tool], servers=[server])
    audit_mock = AsyncMock()
    with patch.object(mcp_service, "_client", return_value=client):
        with patch.object(mcp_service, "_call_mcp_server", new=AsyncMock(return_value={"ok": True})):
            with patch.object(mcp_service, "_log_execution", new=AsyncMock()):
                with patch.object(mcp_service, "_audit_execution", audit_mock):
                    await mcp_service.execute_tool("tool-read", "org-1", {})
    audit_mock.assert_called_once()


@pytest.mark.parametrize(
    "name,description,expected",
    [
        ("get_users", "List users", "read"),
        ("create_user", "Create a user", "write"),
        ("fetch", "Send notification", "write"),
        ("search", None, "read"),
    ],
)
def test_write_tools_classified_conservatively(name, description, expected):
    assert classify_mcp_tool_capability(name, description) == expected


@pytest.mark.asyncio
async def test_cross_org_mcp_tool_access_blocked(mcp_service):
    client = _mock_supabase(tools=[])
    with patch.object(mcp_service, "_client", return_value=client):
        with pytest.raises(ValueError, match="not found"):
            await mcp_service.execute_tool("tool-other-org", "org-1", {})


def test_mcp_openai_tool_name_format():
    name = mcp_openai_tool_name("My Server", "Get Data")
    assert name.startswith("mcp_")
    assert "get_data" in name



@pytest.mark.asyncio
async def test_enabled_tool_on_disabled_imported_server_is_hidden(mcp_service):
    tool = {
        "id": "tool-pending",
        "server_id": "srv-pending",
        "tool_name": "search_records",
        "tool_description": "Search records",
        "capability_tier": "read",
        "enabled": True,
        "input_schema": {"type": "object", "properties": {}},
        "mcp_servers": {
            "server_name": "Imported MCP",
            "enabled": False,
            "activation_state": "pending_review",
        },
    }
    client = _mock_supabase(tools=[tool])
    with patch.object(mcp_service, "_client", return_value=client):
        available = await mcp_service.get_enabled_tools_for_org("org-1")
    assert available == []


@pytest.mark.asyncio
async def test_imported_server_discovery_can_persist_tools_disabled(mcp_service):
    server = {
        "id": "srv-pending",
        "server_name": "Imported MCP",
        "server_url": "https://mcp.example.com/sse",
        "transport": "sse",
        "enabled": False,
        "activation_state": "pending_review",
        "auth_config": {},
    }
    client = _mock_supabase(tools=[], servers=[server])
    with (
        patch.object(mcp_service, "_client", return_value=client),
        patch.object(mcp_service, "_load_server", new=AsyncMock(return_value=server)) as load_server,
        patch.object(
            mcp_service,
            "_list_remote_tools",
            new=AsyncMock(
                return_value=[
                    {
                        "name": "search_records",
                        "description": "Search records",
                        "inputSchema": {"type": "object", "properties": {}},
                    }
                ]
            ),
        ),
        patch("app.services.mcp_catalog_sync.sync_mcp_server_to_catalog"),
        patch("app.connectors.action_catalog.extensions.register_action_schemas"),
    ):
        await mcp_service.discover_tools(
            "srv-pending",
            "org-1",
            allow_disabled_server=True,
        )
    load_server.assert_awaited_once_with(
        "srv-pending",
        "org-1",
        allow_disabled=True,
    )
    inserted = client.table("mcp_tools").insert.call_args
    if inserted is not None:
        assert inserted.args[0]["enabled"] is False



def test_refresh_package_mcp_runtime_removes_disabled_tool_schema() -> None:
    server = {
        "id": "srv-package",
        "server_name": "Package MCP",
        "source_capability_package_id": "pkg-1",
    }
    tool = {
        "id": "tool-1",
        "server_id": "srv-package",
        "tool_name": "search_records",
        "tool_description": "Search records",
        "input_schema": {"type": "object", "properties": {}},
        "capability_tier": "read",
        "enabled": False,
    }
    client = _mock_supabase(tools=[tool], servers=[server])
    with (
        patch("app.services.mcp_catalog_sync.sync_mcp_server_to_catalog") as sync_catalog,
        patch("app.connectors.action_catalog.extensions.unregister_action_schemas") as unregister,
        patch("app.connectors.action_catalog.extensions.register_action_schemas") as register,
    ):
        refresh_package_mcp_runtime_registration(
            client,
            org_id="org-1",
            server_id="srv-package",
        )

    sync_catalog.assert_called_once()
    assert sync_catalog.call_args.kwargs["tools"] == []
    expected_key = mcp_openai_tool_name("Package MCP", "search_records")
    unregister.assert_called_once_with([expected_key])
    register.assert_not_called()

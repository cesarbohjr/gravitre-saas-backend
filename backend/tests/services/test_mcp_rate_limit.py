"""MCP tool calls use the atomic MCP server token bucket, per org and MCP server."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.connectors.dispatch import connector_capacity
from app.services.mcp_client_service import MCPClientService, mcp_input_sha256

_READ_TOOL = {"id": "tool-read", "server_id": "srv-1", "tool_name": "list", "capability_tier": "read", "enabled": True}
_WRITE_TOOL = {**_READ_TOOL, "id": "tool-write", "tool_name": "create", "capability_tier": "write"}
_SERVER = {"id": "srv-1", "server_url": "https://93.184.216.34/mcp", "transport": "streamable_http", "enabled": True, "auth_config": {}}


def _client(*, allowed: bool, approval: dict | None = None) -> MagicMock:
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=allowed)

    def table(name):
        mock = MagicMock()
        if name == "mcp_servers":
            mock.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                _SERVER
            ]
        elif name == "approvals" and approval is not None:
            mock.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                approval
            ]
        return mock

    client.table.side_effect = table
    return client


@pytest.fixture
def service() -> MCPClientService:
    return MCPClientService(settings=SimpleNamespace(connector_secrets_encryption_key="k" * 32))


async def _run(service, client, tool, **kwargs):
    call = AsyncMock(return_value={"ok": True})
    with (
        patch.object(service, "_client", return_value=client),
        patch.object(service, "_load_tool", new=AsyncMock(return_value=tool)),
        patch.object(service, "_call_mcp_server", new=call),
        patch.object(service, "_audit_execution", new=AsyncMock()),
        patch.object(service, "_log_execution", new=AsyncMock()),
    ):
        result = await service.execute_tool(tool["id"], "org-1", {"q": 1}, **kwargs)
    return result, call


def test_mcp_bucket_is_configured() -> None:
    assert connector_capacity("mcp") == (10.0, 2.0)


@pytest.mark.asyncio
async def test_call_within_limit_runs_and_uses_org_server_bucket(service) -> None:
    client = _client(allowed=True)
    result, call = await _run(service, client, _READ_TOOL)
    assert result["status"] == "completed"
    call.assert_awaited_once()
    args = client.rpc.call_args.args
    assert args[0] == "consume_mcp_server_token"
    assert args[1]["p_org_id"] == "org-1"
    assert args[1]["p_step_type"] == "mcp"
    assert args[1]["p_server_id"] == "srv-1"


@pytest.mark.asyncio
async def test_call_over_limit_is_refused_without_calling_server(service) -> None:
    result, call = await _run(service, _client(allowed=False), _READ_TOOL)
    assert result["status"] == "rate_limited"
    call.assert_not_awaited()


@pytest.mark.asyncio
async def test_throttled_write_keeps_its_approval(service) -> None:
    approval = {
        "id": "appr-1",
        "status": "approved",
        "consumed_at": None,
        "context": {"mcp_tool_id": "tool-write", "input_sha256": mcp_input_sha256({"q": 1})},
    }
    client = _client(allowed=False, approval=approval)
    result, call = await _run(service, client, _WRITE_TOOL, approval_id="appr-1")
    assert result["status"] == "rate_limited"
    call.assert_not_awaited()
    assert not any(c.args == ("approvals",) for c in client.table.call_args_list)


@pytest.mark.asyncio
async def test_unapproved_write_still_goes_to_approval_without_spending_tokens(service) -> None:
    client = _client(allowed=False)
    client.table.side_effect = None
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "exec-1"}]
    with patch("app.services.mcp_client_service.create_contract_approval", return_value={"id": "appr-1"}):
        result, call = await _run(service, client, _WRITE_TOOL)
    assert result["status"] == "pending_approval"
    client.rpc.assert_not_called()

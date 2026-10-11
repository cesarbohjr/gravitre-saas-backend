"""MCP tool calls pass the same agent permission check and tool.invoke audit as native tools."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tool_registry import ToolRegistry
from app.services.tool_types import ToolContext, ToolPermissionDeniedError

_AGENT_ID = "11111111-1111-4111-8111-111111111111"


def _ctx(agent_id: str | None) -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(connector_secrets_encryption_key="k" * 32),
        client=MagicMock(),
        org_id="org-1",
        actor_id="22222222-2222-4222-8222-222222222222",
        agent_id=agent_id,
    )


def _service(execute_result: dict) -> MagicMock:
    svc = MagicMock()
    svc.get_enabled_tools_for_org = AsyncMock(
        return_value=[{"name": "mcp_crm_lookup", "mcp_tool_id": "tool-1"}]
    )
    svc.execute_tool = AsyncMock(return_value=execute_result)
    return svc


async def _run(ctx, svc, *, permission_side_effect=None):
    audits: list[str] = []
    with (
        patch("app.services.mcp_client_service.get_mcp_client_service", return_value=svc),
        patch(
            "app.services.tool_service.assert_agent_tool_permission",
            side_effect=permission_side_effect,
        ) as perm,
        patch(
            "app.services.tool_service._write_tool_audit",
            side_effect=lambda _ctx, _action, _cid, audit_action, extra=None: audits.append(audit_action),
        ),
    ):
        result = await ToolRegistry()._execute_mcp_tool(ctx, "mcp_crm_lookup", {"q": "acme"})
    return result, perm, audits


@pytest.mark.asyncio
async def test_agent_without_mcp_permission_is_denied_and_audited() -> None:
    svc = _service({"status": "completed", "result": {"ok": True}})
    result, perm, audits = await _run(
        _ctx(_AGENT_ID),
        svc,
        permission_side_effect=ToolPermissionDeniedError("Agent lacks permission"),
    )
    assert result["success"] is False
    assert result["error_code"] == ToolPermissionDeniedError("x").code
    svc.execute_tool.assert_not_awaited()
    perm.assert_called_once()
    _ctx_arg, action, _cid, connector_type = perm.call_args.args
    assert action == "mcp.mcp_crm_lookup"
    assert connector_type == "mcp"
    assert audits == ["tool.invoke.failed"]


@pytest.mark.asyncio
async def test_permitted_agent_mcp_call_is_audited() -> None:
    svc = _service({"status": "completed", "result": {"ok": True}, "latency_ms": 5})
    result, perm, audits = await _run(_ctx(_AGENT_ID), svc)
    assert result["success"] is True
    perm.assert_called_once()
    assert audits == ["tool.invoke.requested", "tool.invoke.completed"]


@pytest.mark.asyncio
async def test_no_agent_context_keeps_behaviour_but_still_audits() -> None:
    svc = _service({"status": "failed", "error": "remote down"})
    result, perm, audits = await _run(_ctx(None), svc)
    assert result["success"] is False
    svc.execute_tool.assert_awaited_once()
    # assert_agent_tool_permission itself is a no-op without agent_id.
    assert audits == ["tool.invoke.requested", "tool.invoke.failed"]

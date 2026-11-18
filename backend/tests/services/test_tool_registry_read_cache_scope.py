"""ECO-006: tenant/provider credential cache isolation at the real ToolRegistry adapter."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.read_action_result_cache import clear_read_action_result_cache
from app.services.tool_registry import ToolRegistry
from app.services.tool_types import NormalizedResult, ToolContext

ACTION = "hubspot.contacts.search"


@pytest.mark.asyncio
async def test_scoped_provider_read_cache_never_crosses_actor_account_or_environment():
    registry = ToolRegistry.__new__(ToolRegistry)
    registry._registered = {ACTION}
    ctx = ToolContext(
        settings=SimpleNamespace(), client=MagicMock(), org_id="org-a",
        actor_id="alice", agent_id="agent-a", connector_id="conn-a",
        environment_name="production",
    )
    calls = []

    def invoke(context, action, params):
        calls.append((context.actor_id, context.connector_id, context.environment_name))
        return NormalizedResult(
            success=True, action=action, connector_id=context.connector_id,
            data={"read_for": context.actor_id, "account": context.connector_id},
        )

    clear_read_action_result_cache()
    try:
        with patch("app.services.tool_registry.invoke_tool", side_effect=invoke):
            a1 = await registry.execute_invoke_action(ctx=ctx, invoke_action=ACTION, args={"query": "Acme"})
            a2 = await registry.execute_invoke_action(ctx=ctx, invoke_action=ACTION, args={"query": "Acme"})
            bob = await registry.execute_invoke_action(
                ctx=replace(ctx, actor_id="bob"), invoke_action=ACTION, args={"query": "Acme"},
            )
            other_account = await registry.execute_invoke_action(
                ctx=replace(ctx, connector_id="conn-b"), invoke_action=ACTION, args={"query": "Acme"},
            )
            other_env = await registry.execute_invoke_action(
                ctx=replace(ctx, environment_name="preview"), invoke_action=ACTION, args={"query": "Acme"},
            )
        assert a1 == a2
        assert a1["result"]["read_for"] == "alice"
        assert bob["result"]["read_for"] == "bob"
        assert other_account["result"]["account"] == "conn-b"
        assert other_env["success"] is True
        assert calls == [
            ("alice", "conn-a", "production"),
            ("bob", "conn-a", "production"),
            ("alice", "conn-b", "production"),
            ("alice", "conn-a", "preview"),
        ]
    finally:
        clear_read_action_result_cache()


@pytest.mark.asyncio
async def test_unknown_provider_account_never_reuses_cached_result():
    registry = ToolRegistry.__new__(ToolRegistry)
    registry._registered = {ACTION}
    ctx = ToolContext(
        settings=SimpleNamespace(), client=MagicMock(), org_id="org-a",
        actor_id="alice", connector_id=None,
    )
    calls = []

    def invoke(_context, action, _params):
        calls.append(action)
        return NormalizedResult(
            success=True, action=action, data={"request_number": len(calls)},
        )

    clear_read_action_result_cache()
    try:
        with patch("app.services.tool_registry.invoke_tool", side_effect=invoke):
            first = await registry.execute_invoke_action(ctx=ctx, invoke_action=ACTION, args={"query": "Acme"})
            second = await registry.execute_invoke_action(ctx=ctx, invoke_action=ACTION, args={"query": "Acme"})
        assert first["result"]["request_number"] == 1
        assert second["result"]["request_number"] == 2
        assert calls == [ACTION, ACTION]
    finally:
        clear_read_action_result_cache()

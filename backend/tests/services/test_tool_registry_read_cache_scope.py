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
TOOL = "hubspot_search_contacts"


@pytest.fixture(params=["exact", "named"])
def read_route(request):
    registry = ToolRegistry()
    if request.param == "exact":
        async def execute(ctx, args):
            return await registry.execute_invoke_action(ctx=ctx, invoke_action=ACTION, args=args)

        return execute, "app.services.tool_service.invoke_tool"

    async def execute(ctx, args):
        return await registry.execute_tool(ctx=ctx, tool_name=TOOL, args=args)

    return execute, "app.services.tool_registry.invoke_tool"


@pytest.mark.asyncio
async def test_scoped_provider_read_cache_never_crosses_actor_account_or_environment(read_route):
    execute, boundary = read_route
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
        with patch(boundary, side_effect=invoke):
            a1 = await execute(ctx, {"query": "Acme"})
            a2 = await execute(ctx, {"query": "Acme"})
            bob = await execute(
                replace(ctx, actor_id="bob"), {"query": "Acme"},
            )
            other_account = await execute(
                replace(ctx, connector_id="conn-b"), {"query": "Acme"},
            )
            other_env = await execute(
                replace(ctx, environment_name="preview"), {"query": "Acme"},
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
async def test_unknown_provider_account_never_reuses_cached_result(read_route):
    execute, boundary = read_route
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
        with patch(boundary, side_effect=invoke):
            first = await execute(ctx, {"query": "Acme"})
            second = await execute(ctx, {"query": "Acme"})
        assert first["result"]["request_number"] == 1
        assert second["result"]["request_number"] == 2
        assert calls == [ACTION, ACTION]
    finally:
        clear_read_action_result_cache()


@pytest.mark.asyncio
async def test_untrusted_connector_argument_cannot_select_a_cached_account():
    registry = ToolRegistry.__new__(ToolRegistry)
    registry._registered = {ACTION}
    ctx = ToolContext(
        settings=SimpleNamespace(), client=MagicMock(), org_id="org-a",
        actor_id="alice", connector_id="conn-a",
    )
    hits = []

    def invoke(_ctx, action, params):
        hits.append(dict(params))
        return NormalizedResult(
            success=True, action=action, connector_id="conn-a",
            data={"request_number": len(hits)},
        )

    clear_read_action_result_cache()
    try:
        with patch("app.services.tool_service.invoke_tool", side_effect=invoke):
            for _ in range(2):
                observed = await registry.execute_invoke_action(
                    ctx=ctx, invoke_action=ACTION,
                    args={"connector_id": "conn-b", "query": "Acme"},
                )
        assert observed["result"]["request_number"] == 2
        assert len(hits) == 2
    finally:
        clear_read_action_result_cache()


@pytest.mark.asyncio
async def test_result_from_different_account_is_never_cached_under_context_account(read_route):
    execute, boundary = read_route
    ctx = ToolContext(
        settings=SimpleNamespace(), client=MagicMock(), org_id="org-a",
        actor_id="alice", connector_id="conn-a",
    )
    results = [
        NormalizedResult(success=True, action=ACTION, connector_id="conn-b", data={"observed": 1}),
        NormalizedResult(success=True, action=ACTION, connector_id="conn-a", data={"observed": 2}),
    ]

    clear_read_action_result_cache()
    try:
        with patch(boundary, side_effect=results) as invoke:
            first = await execute(ctx, {"query": "Acme"})
            second = await execute(ctx, {"query": "Acme"})
            third = await execute(ctx, {"query": "Acme"})
        assert first["result"]["observed"] == 1
        assert second["result"]["observed"] == 2
        assert third == second
        assert invoke.call_count == 2
    finally:
        clear_read_action_result_cache()

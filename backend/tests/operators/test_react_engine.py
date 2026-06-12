from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators.react_engine import (
    DEFAULT_MAX_ITERATIONS,
    ReActEngine,
    ReActStatus,
    resolve_permitted_tools,
)
from app.services.tool_types import ToolContext


@pytest.fixture
def tool_ctx() -> ToolContext:
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32)
    client = MagicMock()
    return ToolContext(
        settings=settings,
        client=client,
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-1",
        task_id="job-1",
    )


@pytest.fixture
def engine() -> ReActEngine:
    settings = SimpleNamespace(disable_ai=False, ai_pii_redaction_enabled=False)
    registry = MagicMock()
    registry.list_connected_integrations.return_value = ["hubspot"]
    registry.get_tools_for_agent.return_value = [
        {
            "type": "function",
            "function": {
                "name": "hubspot_search_contacts",
                "description": "search",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
            },
        }
    ]
    react = ReActEngine(settings=settings, registry=registry)
    react.router = MagicMock()
    react.router._openai = AsyncMock()
    return react


def _choice(content: str = "", tool_calls: list | None = None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    return SimpleNamespace(message=message, finish_reason="stop")


def _tool_call(name: str, args: str, call_id: str = "call-1"):
    fn = SimpleNamespace(name=name, arguments=args)
    return SimpleNamespace(id=call_id, function=fn)


def test_default_max_iterations_is_ten():
    assert DEFAULT_MAX_ITERATIONS == 10


@pytest.mark.asyncio
async def test_run_no_tools_available_uses_reasoning_only(engine: ReActEngine, tool_ctx: ToolContext):
    engine.registry.get_tools_for_agent.return_value = []
    engine.router._openai.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(choices=[_choice("Planned weekly invoice monitoring steps.")])
    )
    with patch("app.operators.react_engine.moderate_input", new=AsyncMock()):
        with patch("app.operators.react_engine.write_audit_event"):
            result = await engine.run(
                ctx=tool_ctx,
                task="Monitor overdue invoices",
                permitted_tools=["hubspot"],
                connected_integrations=[],
            )
    assert result.status == ReActStatus.COMPLETED
    assert len(result.trace) == 1
    assert result.trace[0].thought
    assert "invoice" in result.answer.lower()


@pytest.mark.asyncio
async def test_run_writes_audit_event_per_iteration(engine: ReActEngine, tool_ctx: ToolContext):
    engine.registry.execute_tool = AsyncMock(return_value={"success": True, "result": {"ok": True}})
    engine.router._openai.chat.completions.create = AsyncMock(
        side_effect=[
            SimpleNamespace(
                choices=[
                    _choice(
                        "Searching.",
                        tool_calls=[_tool_call("hubspot_search_contacts", '{"query":"acme"}')],
                    )
                ]
            ),
            SimpleNamespace(choices=[_choice("Finished.")]),
        ]
    )
    with patch("app.operators.react_engine.moderate_input", new=AsyncMock()):
        with patch("app.operators.react_engine.write_audit_event") as audit_mock:
            result = await engine.run(
                ctx=tool_ctx,
                task="Find contact",
                permitted_tools=["hubspot"],
                connected_integrations=["hubspot"],
                max_iterations=5,
                audit_resource_id="job-1",
            )
    assert result.status == ReActStatus.COMPLETED
    assert audit_mock.call_count >= 2
    actions = [call.kwargs["action"] for call in audit_mock.call_args_list]
    assert all(action == "agent.react.iteration" for action in actions)
    tool_audit = [
        call.kwargs["metadata"]["status"]
        for call in audit_mock.call_args_list
        if call.kwargs.get("metadata", {}).get("status") == "tool_call"
    ]
    assert tool_audit == ["tool_call"]


def test_react_result_to_dict_includes_trace(engine: ReActEngine):
    from app.operators.react_engine import ReActResult, ReActTraceStep

    result = ReActResult(
        status=ReActStatus.COMPLETED,
        answer="ok",
        trace=[
            ReActTraceStep(iteration=1, thought="step 1", tool_name="hubspot_search_contacts", tool_success=True),
        ],
        iterations=1,
        tool_calls=[{"tool": "hubspot_search_contacts"}],
    )
    payload = result.to_dict()
    assert payload["status"] == "completed"
    assert len(payload["trace"]) == 1
    assert payload["trace"][0]["toolName"] == "hubspot_search_contacts"


@pytest.mark.asyncio
async def test_execute_tool_call_delegates_to_registry(engine: ReActEngine, tool_ctx: ToolContext):
    engine.registry.execute_tool = AsyncMock(return_value={"success": True, "result": {"ok": True}})
    result = await engine._execute_tool_call(
        tool_ctx,
        "hubspot_search_contacts",
        {"query": "acme"},
    )
    assert result["success"] is True
    engine.registry.execute_tool.assert_awaited_once_with(
        ctx=tool_ctx,
        tool_name="hubspot_search_contacts",
        args={"query": "acme"},
    )


@pytest.mark.asyncio
async def test_execute_tool_call_rejects_disallowed_tool(engine: ReActEngine, tool_ctx: ToolContext):
    engine.registry.execute_tool = AsyncMock()
    result = await engine._execute_tool_call(
        tool_ctx,
        "slack_send_message",
        {"channel": "#x", "message": "hi"},
        allowed_tool_names={"hubspot_search_contacts"},
    )
    assert result["success"] is False
    assert result["error_code"] == "tool_not_available"
    engine.registry.execute_tool.assert_not_called()


@pytest.mark.asyncio
async def test_run_surfaces_tool_errors_in_trace_without_crashing(
    engine: ReActEngine, tool_ctx: ToolContext
):
    engine.registry.execute_tool = AsyncMock(
        return_value={"success": False, "error": "HubSpot rate limited", "tool": "hubspot_search_contacts"}
    )
    engine.router._openai.chat.completions.create = AsyncMock(
        side_effect=[
            SimpleNamespace(
                choices=[
                    _choice(
                        "Searching.",
                        tool_calls=[_tool_call("hubspot_search_contacts", '{"query":"acme"}')],
                    )
                ]
            ),
            SimpleNamespace(choices=[_choice("Could not reach HubSpot; try again later.")]),
        ]
    )
    with patch("app.operators.react_engine.moderate_input", new=AsyncMock()):
        result = await engine.run(
            ctx=tool_ctx,
            task="Find contact",
            permitted_tools=["hubspot"],
            connected_integrations=["hubspot"],
            max_iterations=5,
        )
    assert result.status == ReActStatus.COMPLETED
    assert result.trace[0].tool_success is False
    assert "rate limited" in (result.trace[0].observation or "")


@pytest.mark.asyncio
async def test_run_completes_on_final_answer(engine: ReActEngine, tool_ctx: ToolContext):
    engine.router._openai.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(choices=[_choice("Done — contact updated.")])
    )
    with patch("app.operators.react_engine.moderate_input", new=AsyncMock()):
        result = await engine.run(
            ctx=tool_ctx,
            task="Update the contact",
            permitted_tools=["hubspot"],
            connected_integrations=["hubspot"],
            max_iterations=3,
        )
    assert result.status == ReActStatus.COMPLETED
    assert "contact updated" in result.answer
    assert result.iterations == 1


@pytest.mark.asyncio
async def test_run_executes_tool_then_completes(engine: ReActEngine, tool_ctx: ToolContext):
    engine.registry.execute_tool = AsyncMock(
        return_value={"success": True, "result": {"contacts": [{"id": "1"}]}}
    )
    engine.router._openai.chat.completions.create = AsyncMock(
        side_effect=[
            SimpleNamespace(
                choices=[
                    _choice(
                        "Searching HubSpot.",
                        tool_calls=[_tool_call("hubspot_search_contacts", '{"query":"acme"}')],
                    )
                ]
            ),
            SimpleNamespace(choices=[_choice("Found contact acme@example.com.")]),
        ]
    )
    with patch("app.operators.react_engine.moderate_input", new=AsyncMock()):
        result = await engine.run(
            ctx=tool_ctx,
            task="Find acme contact",
            permitted_tools=["hubspot"],
            connected_integrations=["hubspot"],
            max_iterations=5,
        )
    assert result.status == ReActStatus.COMPLETED
    assert result.iterations == 2
    assert len(result.tool_calls) == 1
    engine.registry.execute_tool.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_needs_human_input(engine: ReActEngine, tool_ctx: ToolContext):
    engine.router._openai.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[_choice("NEEDS_HUMAN_INPUT: Which deal stage should I use?")]
        )
    )
    with patch("app.operators.react_engine.moderate_input", new=AsyncMock()):
        result = await engine.run(
            ctx=tool_ctx,
            task="Move deal to next stage",
            permitted_tools=["hubspot"],
            connected_integrations=["hubspot"],
        )
    assert result.status == ReActStatus.NEEDS_HUMAN_INPUT
    assert "deal stage" in result.answer


@pytest.mark.asyncio
async def test_run_max_iterations_reached(engine: ReActEngine, tool_ctx: ToolContext):
    engine.registry.execute_tool = AsyncMock(return_value={"success": True, "result": {}})
    engine.router._openai.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                _choice(
                    "still working",
                    tool_calls=[_tool_call("hubspot_search_contacts", '{"query":"x"}', "c1")],
                )
            ]
        )
    )
    with patch("app.operators.react_engine.moderate_input", new=AsyncMock()):
        result = await engine.run(
            ctx=tool_ctx,
            task="Loop forever",
            permitted_tools=["hubspot"],
            connected_integrations=["hubspot"],
            max_iterations=2,
        )
    assert result.status == ReActStatus.MAX_ITERATIONS_REACHED
    assert result.iterations == 2


@pytest.mark.asyncio
async def test_run_permission_denied_returns_needs_human(engine: ReActEngine, tool_ctx: ToolContext):
    engine.registry.execute_tool = AsyncMock(
        return_value={
            "success": False,
            "error": "Agent lacks permission",
            "error_code": "permission_denied",
        }
    )
    engine.router._openai.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                _choice(
                    "",
                    tool_calls=[_tool_call("hubspot_search_contacts", '{"query":"acme"}')],
                )
            ]
        )
    )
    with patch("app.operators.react_engine.moderate_input", new=AsyncMock()):
        result = await engine.run(
            ctx=tool_ctx,
            task="Find contact in HubSpot",
            permitted_tools=["hubspot"],
            connected_integrations=["hubspot"],
        )
    assert result.status == ReActStatus.NEEDS_HUMAN_INPUT
    assert "permission" in result.answer.lower()


def test_resolve_permitted_tools_from_agent_systems():
    allowed = resolve_permitted_tools({"systems": ["hubspot", "slack"]})
    assert allowed == ["hubspot", "slack"]


def test_resolve_permitted_tools_explicit_override():
    allowed = resolve_permitted_tools({"systems": ["hubspot"]}, explicit=["jira"])
    assert allowed == ["jira"]

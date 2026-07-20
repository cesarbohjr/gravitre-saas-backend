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
    registry.get_available_tools = AsyncMock(
        return_value=[{"type": "function", "function": {"name": "hubspot_search_contacts"}}]
    )
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
    engine.registry.get_available_tools = AsyncMock(return_value=[])
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
    with patch(
        "app.services.react_write_gate.tool_requires_user_write_approval",
        return_value=(False, "hubspot.contacts.search", "hubspot", "Search"),
    ):
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
async def test_streaming_extends_cap_when_routing_escalates(
    engine: ReActEngine, tool_ctx: ToolContext
):
    """Mid-turn escalate must raise the iteration ceiling (routing wave Bugbot High)."""
    from app.services.assistant_routing_tier import RoutingControl

    ctrl = RoutingControl(tier="simple", model="gpt-4o-mini", max_iterations=1, pinned_fast=False)
    call_n = {"n": 0}

    async def _chat(_messages, _tools, _model):
        call_n["n"] += 1
        if call_n["n"] == 1:
            # Escalate after first model call so subsequent rounds honor new max.
            assert ctrl.escalate("research", "test_mid_turn") is True
            assert ctrl.max_iterations >= 12
            return SimpleNamespace(
                choices=[
                    _choice(
                        "",
                        tool_calls=[_tool_call("hubspot_search_contacts", '{"query":"a"}', "c1")],
                    )
                ]
            )
        if call_n["n"] == 2:
            return SimpleNamespace(
                choices=[
                    _choice(
                        "",
                        tool_calls=[_tool_call("hubspot_search_contacts", '{"query":"b"}', "c2")],
                    )
                ]
            )
        return SimpleNamespace(choices=[_choice("Finished after escalate")])

    engine.registry.execute_tool = AsyncMock(return_value={"success": True, "result": {}})
    with patch.object(engine, "_chat_with_tools", AsyncMock(side_effect=_chat)):
        with patch("app.operators.react_engine.moderate_input", new=AsyncMock()):
            with patch("app.operators.react_engine.write_audit_event"):
                done = None
                async for event in engine.run_streaming(
                    ctx=tool_ctx,
                    task="Keep searching",
                    permitted_tools=["hubspot"],
                    connected_integrations=["hubspot"],
                    max_iterations=1,
                    routing_control=ctrl,
                ):
                    if event.kind == "done":
                        done = event.react_result

    assert done is not None
    assert done.status == ReActStatus.COMPLETED
    assert call_n["n"] >= 3
    assert done.iterations >= 3


@pytest.mark.asyncio
async def test_run_auth_expired_surfaces_formatted_error(engine: ReActEngine, tool_ctx: ToolContext):
    """Wave 3 — connector auth failures short-circuit with actionable copy, not LLM narration."""
    engine.registry.get_available_tools = AsyncMock(
        return_value=[{"type": "function", "function": {"name": "hubspot_search_contacts"}}]
    )
    engine.registry.execute_tool = AsyncMock(
        return_value={
            "success": False,
            "error": "OAuth not completed",
            "error_code": "auth_expired",
            "action": "hubspot.contacts.search",
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
    assert "/connectors" in result.answer
    assert "Authentication expired" in result.answer


@pytest.mark.asyncio
async def test_parallel_independent_reads_share_one_batch(engine: ReActEngine, tool_ctx: ToolContext):
    """Phase 2 — consecutive read tools in one model turn run via asyncio.gather."""
    import asyncio

    engine.registry.get_available_tools = AsyncMock(
        return_value=[
            {"type": "function", "function": {"name": "hubspot_search_contacts"}},
            {"type": "function", "function": {"name": "assistant_connector_status"}},
        ]
    )
    started: list[float] = []
    gate = asyncio.Event()

    async def _slow_exec(*, ctx, tool_name, args):  # noqa: ANN001
        started.append(asyncio.get_running_loop().time())
        if len(started) == 1:
            await gate.wait()
        else:
            gate.set()
        await asyncio.sleep(0.05)
        return {"success": True, "tool": tool_name, "result": {}}

    engine.registry.execute_tool = AsyncMock(side_effect=_slow_exec)

    def _requires(name, _reg):
        return (False, "", "", name)

    engine.router._openai.chat.completions.create = AsyncMock(
        side_effect=[
            SimpleNamespace(
                choices=[
                    _choice(
                        "",
                        tool_calls=[
                            _tool_call("hubspot_search_contacts", '{"query":"a"}', "c1"),
                            _tool_call("assistant_connector_status", "{}", "c2"),
                        ],
                    )
                ]
            ),
            SimpleNamespace(choices=[_choice("Both reads done.")]),
        ]
    )
    with patch(
        "app.services.react_write_gate.tool_requires_user_write_approval",
        side_effect=_requires,
    ):
        with patch("app.operators.react_engine.moderate_input", new=AsyncMock()):
            with patch("app.operators.react_engine.write_audit_event"):
                result = await engine.run(
                    ctx=tool_ctx,
                    task="Check HubSpot and connector status",
                    permitted_tools=["hubspot"],
                    connected_integrations=["hubspot"],
                )
    assert result.status == ReActStatus.COMPLETED
    assert len(result.tool_calls) == 2
    assert all(c.get("parallel_batch") for c in result.tool_calls)
    # Overlap: second tool started before first finished (gate handshake).
    assert len(started) == 2


def test_resolve_permitted_tools_from_agent_systems():
    allowed = resolve_permitted_tools({"systems": ["hubspot", "slack"]})
    assert allowed == ["hubspot", "slack"]


def test_resolve_permitted_tools_explicit_override():
    allowed = resolve_permitted_tools({"systems": ["hubspot"]}, explicit=["jira"])
    assert allowed == ["jira"]

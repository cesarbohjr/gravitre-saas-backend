"""Tests for universal research policy in AgentIntelligence system prompts."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators.agent_intelligence import (
    RESEARCH_POLICY,
    AgentIntelligence,
)
from app.operators.assistant_mode_config import resolve_assistant_tool_names
from app.operators.react_engine import ReActResult, ReActStatus
from app.operators.stream_events import AssistantStreamComplete


@pytest.fixture
def intelligence() -> AgentIntelligence:
    settings = SimpleNamespace(disable_ai=False, rag_top_k=5)
    react = MagicMock()
    react.run = AsyncMock(
        return_value=ReActResult(
            status=ReActStatus.COMPLETED,
            answer="done",
            tool_calls=[],
        )
    )
    unified = MagicMock()
    unified.retrieve = AsyncMock(
        return_value=SimpleNamespace(
            rag_sources=[{"id": "c1", "content": "Pricing FAQ", "score": 0.9, "source": "KB"}],
            rag_section="<knowledge_base>[]</knowledge_base>",
            org_context={"connectedIntegrations": ["hubspot"], "orgName": "Acme"},
            memory_section="",
            memory_context={},
            sources=[],
            metrics={},
        )
    )
    intel = AgentIntelligence(settings=settings, react_engine=react, unified_retrieval=unified)
    intel.tool_registry = MagicMock()
    intel.tool_registry.list_connected_integrations.return_value = ["hubspot"]
    intel.tool_registry.get_tools_for_agent.return_value = []
    return intel


def _agent_row() -> dict:
    return {
        "id": "agent-1",
        "name": "Sales Agent",
        "role": "Sales",
        "purpose": "Qualify inbound leads",
        "systems": ["hubspot"],
        "config": {},
    }


def test_system_prompt_includes_research_policy():
    ai = AgentIntelligence()
    prompt = ai._build_system_prompt(
        "agent_task",
        _agent_row(),
        [{"source": "KB", "content": "Policy doc", "score": 0.8}],
        {"orgName": "Acme", "connectedIntegrations": ["hubspot"]},
    )
    assert "## Research Policy" in prompt
    assert "Prefer internal knowledge" in prompt
    assert RESEARCH_POLICY.strip() in prompt


@pytest.mark.asyncio
async def test_policy_appears_for_operator_async(intelligence: AgentIntelligence):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    with patch("app.operators.agent_intelligence.write_audit_event"):
        await intelligence.execute_task(
            org_id="org-1",
            agent=_agent_row(),
            task="Check pipeline",
            client=client,
            parameters={"surface": "operator"},
        )
    prompt = intelligence.react_engine.run.await_args.kwargs["system_prompt"]
    assert "## Research Policy" in prompt


@pytest.mark.asyncio
async def test_policy_appears_for_agent_jobs(intelligence: AgentIntelligence):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    with patch("app.operators.agent_intelligence.write_audit_event"):
        await intelligence.execute_task(
            org_id="org-1",
            agent=_agent_row(),
            task="Run task",
            client=client,
            parameters={"surface": "agent_task"},
        )
    prompt = intelligence.react_engine.run.await_args.kwargs["system_prompt"]
    assert "FUSE them into one" in prompt
    assert "coherent answer" in prompt


@pytest.mark.asyncio
async def test_policy_appears_for_workflow_nodes(intelligence: AgentIntelligence):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    with patch("app.operators.agent_intelligence.write_audit_event"):
        await intelligence.execute_task(
            org_id="org-1",
            agent=_agent_row(),
            task="Workflow step",
            client=client,
            parameters={"surface": "workflow"},
            run_id="run-1",
        )
    prompt = intelligence.react_engine.run.await_args.kwargs["system_prompt"]
    assert "do not fabricate or guess at external facts" in prompt


@pytest.mark.asyncio
async def test_policy_appears_for_swarm_subtasks(intelligence: AgentIntelligence):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    with patch("app.operators.agent_intelligence.write_audit_event"):
        await intelligence.execute_task(
            org_id="org-1",
            agent=_agent_row(),
            task="Swarm subtask",
            client=client,
            parameters={"surface": "swarm"},
        )
    prompt = intelligence.react_engine.run.await_args.kwargs["system_prompt"]
    assert "## Your Internal Knowledge" in prompt
    assert "## Research Policy" in prompt


@pytest.mark.asyncio
async def test_policy_appears_for_assistant_streaming(intelligence: AgentIntelligence):
    client = MagicMock()
    intelligence.tool_registry.execute_tool = AsyncMock()
    captured: dict[str, str] = {}

    async def fake_streaming(**kwargs):
        captured["system_prompt"] = kwargs.get("system_prompt", "")
        yield SimpleNamespace(
            kind="done",
            react_result=ReActResult(status=ReActStatus.COMPLETED, answer="ok"),
        )

    intelligence.react_engine.run_streaming = fake_streaming

    with patch("app.operators.agent_intelligence.get_org_context_service") as org_service:
        org_service.return_value.get_context_bundle.return_value = (
            {"orgName": "Acme", "connectedIntegrations": ["hubspot"]},
            "Org block",
        )
        with patch("app.operators.agent_intelligence.tool_knowledge_base", AsyncMock(return_value={"results": []})):
            with patch("app.operators.agent_intelligence.maybe_summarize_history", AsyncMock(return_value=SimpleNamespace(messages=[], summary=None, summary_updated=False))):
                events = []
                async for event in intelligence.execute_task_streaming(
                    org_id="org-1",
                    user_id="user-1",
                    query="What is happening externally?",
                    mode="standard",
                    requested_tools=None,
                    client=client,
                ):
                    events.append(event)

    assert captured["system_prompt"]
    assert "## Research Policy" in captured["system_prompt"]
    assert any(isinstance(event, AssistantStreamComplete) for event in events)


@pytest.mark.asyncio
async def test_policy_appears_for_agent_chat_ui(intelligence: AgentIntelligence):
    scoped_tools = [
        "knowledge_base",
        "agent_status",
        "connector_status",
        "workflow_runs",
        "search_web",
    ]
    client = MagicMock()
    captured: dict[str, str] = {}

    async def fake_streaming(**kwargs):
        captured["system_prompt"] = kwargs.get("system_prompt", "")
        yield SimpleNamespace(
            kind="done",
            react_result=ReActResult(status=ReActStatus.COMPLETED, answer="ok"),
        )

    intelligence.react_engine.run_streaming = fake_streaming

    with patch("app.operators.agent_intelligence.resolve_agent_record", return_value=_agent_row()):
        with patch("app.operators.agent_intelligence.get_org_context_service") as org_service:
            org_service.return_value.get_context_bundle.return_value = (
                {"orgName": "Acme", "connectedIntegrations": ["hubspot"]},
                "Org block",
            )
            with patch("app.operators.agent_intelligence.tool_knowledge_base", AsyncMock(return_value={"results": []})):
                with patch("app.operators.agent_intelligence.maybe_summarize_history", AsyncMock(return_value=SimpleNamespace(messages=[], summary=None, summary_updated=False))):
                    with patch("app.services.agent_memory_service.build_task_retrieval_context", return_value={}):
                        with patch("app.services.agent_memory_service.format_retrieval_prompt_section", return_value=""):
                            async for _ in intelligence.execute_task_streaming(
                                org_id="org-1",
                                user_id="user-1",
                                query="Pipeline risks",
                                mode="agent",
                                requested_tools=scoped_tools,
                                agent_id="agent-1",
                                client=client,
                            ):
                                pass

    assert "## Research Policy" in captured["system_prompt"]
    assert resolve_assistant_tool_names("agent", scoped_tools)


def test_policy_holds_when_web_search_unavailable():
    ai = AgentIntelligence()
    prompt = ai._build_system_prompt(
        "assistant",
        None,
        [],
        "[sample org context]",
    )
    assert "If web search is not available to you in this" in prompt
    assert "do not fabricate or guess at external facts" in prompt
    fast_tools = resolve_assistant_tool_names("fast", None)
    assert "search_web" not in fast_tools


def test_no_persona_conflicts_silently_overridden():
    """Step 3 found no conflicting persona research language in agent_prompts.py."""
    ai = AgentIntelligence()
    prompt = ai._build_system_prompt(
        "agent_task",
        _agent_row(),
        [],
        {"orgName": "Acme"},
    )
    assert "## Research Policy" in prompt
    assert "Sales Agent" in prompt


def test_execute_task_and_streaming_share_build_system_prompt():
    from app.operators import agent_intelligence as module

    text = open(module.__file__, encoding="utf-8").read()
    assert text.count("def _build_system_prompt(") == 1
    assert text.count("self._build_system_prompt(") >= 2
    assert "system_prompt = self._build_system_prompt(" in text

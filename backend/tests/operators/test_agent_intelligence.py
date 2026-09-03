from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators.agent_intelligence import (
    AgentIntelligence,
    AgentResult,
    load_agent_task_history,
    load_org_context,
    select_model_for_agent,
)
from app.operators.agent_prompts import build_agent_system_prompt, normalize_agent_role
from app.operators.react_engine import ReActResult, ReActStatus, ReActTraceStep
from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from tests.conftest import patch_agent_streaming_dialogue_pipeline


@pytest.fixture
def agent_row() -> dict:
    return {
        "id": "agent-1",
        "name": "Sales Agent",
        "role": "Sales",
        "purpose": "Qualify inbound leads",
        "systems": ["hubspot", "slack"],
        "model": "gpt-5.5",
        "config": {},
    }


@pytest.fixture
def intelligence() -> AgentIntelligence:
    settings = SimpleNamespace(disable_ai=False, rag_top_k=5)
    react = MagicMock()
    react.run = AsyncMock(
        return_value=ReActResult(
            status=ReActStatus.COMPLETED,
            answer="Contact updated in HubSpot.",
            iterations=2,
            tool_calls=[{"tool": "hubspot_update_deal", "result": {"success": True}}],
            trace=[ReActTraceStep(iteration=1, tool_name="hubspot_update_deal", tool_success=True)],
        )
    )
    rag = MagicMock()
    rag.query = AsyncMock(
        return_value=SimpleNamespace(
            chunks=[
                SimpleNamespace(id="c1", content="Pricing FAQ", score=0.9, source="KB"),
            ]
        )
    )
    unified = MagicMock()
    unified.retrieve = AsyncMock(
        return_value=SimpleNamespace(
            rag_sources=[{"id": "c1", "content": "Pricing FAQ", "score": 0.9, "source": "KB"}],
            rag_section="<knowledge_base>[]</knowledge_base>",
            org_context={"connectedIntegrations": ["hubspot"]},
            memory_section="",
            memory_context={},
            sources=[],
            metrics={},
        )
    )
    intel = AgentIntelligence(settings=settings, react_engine=react, rag_service=rag, unified_retrieval=unified)
    intel.tool_registry = MagicMock()
    intel.tool_registry.list_connected_integrations.return_value = ["hubspot"]
    intel.tool_registry.enrich_connected_integrations = AsyncMock(
        side_effect=lambda _client, _org_id, connected: connected
    )
    intel.tool_registry.get_available_tools = AsyncMock(
        return_value=[{"type": "function", "function": {"name": "hubspot_update_deal"}}]
    )
    intel.tool_registry.get_tools_for_agent.return_value = [
        {"type": "function", "function": {"name": "hubspot_update_deal"}},
    ]
    return intel


@pytest.mark.asyncio
async def test_get_agent_tools_delegates_to_registry(agent_row: dict, intelligence: AgentIntelligence):
    intelligence.tool_registry.enrich_connected_integrations = AsyncMock(return_value=["hubspot"])
    intelligence.tool_registry.get_available_tools = AsyncMock(
        return_value=[{"type": "function", "function": {"name": "hubspot_search_contacts"}}]
    )
    tools = await intelligence.get_agent_tools(
        agent_row,
        ["hubspot"],
        org_id="org-1",
        client=MagicMock(),
    )
    intelligence.tool_registry.get_available_tools.assert_awaited_once()
    assert tools[0]["function"]["name"] == "hubspot_search_contacts"


@pytest.mark.asyncio
async def test_execute_task_passes_connected_integrations(agent_row: dict, intelligence: AgentIntelligence):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    with patch("app.operators.agent_intelligence.write_audit_event"):
        await intelligence.execute_task(
            org_id="org-1",
            agent=agent_row,
            task="Find lead",
            client=client,
        )
    call_kwargs = intelligence.react_engine.run.await_args.kwargs
    assert call_kwargs["connected_integrations"] == ["hubspot"]


@pytest.mark.asyncio
async def test_execute_task_queries_rag_with_agent_id(agent_row: dict, intelligence: AgentIntelligence):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    intelligence.unified_retrieval.retrieve = AsyncMock(
        return_value=SimpleNamespace(
            rag_sources=[{"id": "c1", "content": "Pricing FAQ", "score": 0.9, "source": "KB"}],
            rag_section="<knowledge_base>[]</knowledge_base>",
            org_context={"connectedIntegrations": []},
            memory_section="",
            memory_context={},
            sources=[],
            metrics={},
        )
    )
    with patch("app.operators.agent_intelligence.write_audit_event"):
        with patch("app.operators.agent_intelligence.load_agent_task_history", return_value=[]):
            await intelligence.execute_task(
                org_id="org-1",
                agent=agent_row,
                task="What is our pricing?",
                client=client,
            )
    intelligence.unified_retrieval.retrieve.assert_awaited_once()
    _, kwargs = intelligence.unified_retrieval.retrieve.await_args
    assert kwargs["org_id"] == "org-1"
    assert kwargs["query"] == "What is our pricing?"


@pytest.mark.asyncio
async def test_execute_task_empty_kb_handled_gracefully(agent_row: dict, intelligence: AgentIntelligence):
    client = MagicMock()
    intelligence.unified_retrieval.retrieve = AsyncMock(
        return_value=SimpleNamespace(
            rag_sources=[],
            rag_section="",
            org_context={"connectedIntegrations": []},
            memory_section="",
            memory_context={},
            sources=[],
            metrics={},
        )
    )
    with patch("app.operators.agent_intelligence.write_audit_event"):
        with patch("app.operators.agent_intelligence.load_agent_task_history", return_value=[]):
            result = await intelligence.execute_task(
                org_id="org-1",
                agent=agent_row,
                task="Unknown policy question",
                client=client,
            )
    assert result.rag_sources == []
    task_prompt = intelligence.react_engine.run.await_args.kwargs["task"]
    assert "<knowledge_base>" not in task_prompt
    system_prompt = intelligence.react_engine.run.await_args.kwargs["system_prompt"]
    assert "No knowledge-base excerpts" in system_prompt


@pytest.mark.asyncio
async def test_execute_task_rag_sources_cited_in_output(agent_row: dict, intelligence: AgentIntelligence):
    client = MagicMock()
    intelligence.unified_retrieval.retrieve = AsyncMock(
        return_value=SimpleNamespace(
            rag_sources=[{"id": "chunk-1", "content": "Refund policy text", "score": 0.88, "source": "Policy Doc"}],
            rag_section="<knowledge_base>[]</knowledge_base>",
            org_context={"connectedIntegrations": []},
            memory_section="",
            memory_context={},
            sources=[],
            metrics={},
        )
    )
    with patch("app.operators.agent_intelligence.write_audit_event"):
        with patch("app.operators.agent_intelligence.load_agent_task_history", return_value=[]):
            result = await intelligence.execute_task(
                org_id="org-1",
                agent=agent_row,
                task="Summarize refund policy",
                client=client,
            )
    assert len(result.rag_sources) == 1
    assert result.rag_sources[0]["source"] == "Policy Doc"
    handoff = result.to_handoff_dict()
    assert handoff["rag_sources"][0]["source"] == "Policy Doc"
    assert result.decision is not None
    assert result.decision["ragSources"][0]["source"] == "Policy Doc"


@pytest.mark.asyncio
async def test_execute_task_runs_react_with_context(agent_row: dict, intelligence: AgentIntelligence):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "org-1", "name": "Acme"}]
    )
    with patch("app.operators.agent_intelligence.write_audit_event"):
        with patch("app.operators.agent_intelligence.load_agent_task_history", return_value=[]):
            result = await intelligence.execute_task(
                org_id="org-1",
                agent=agent_row,
                task="Update deal stage",
                briefing={"deal": {"id": "d1"}},
                parameters={"include_department_rag": False},
                actor_id="user-1",
                run_id="run-1",
                client=client,
            )
    assert result.summary == "Contact updated in HubSpot."
    assert result.confidence >= 70
    assert result.briefing_received is True
    assert len(result.rag_sources) == 1
    intelligence.react_engine.run.assert_awaited_once()
    call_kwargs = intelligence.react_engine.run.await_args.kwargs
    assert "handoff_briefing" in call_kwargs["task"]
    assert call_kwargs["model"] == "gpt-5.5"
    assert result.execution_mode == "tools_executed"
    assert result.tool_call_count == 1
    assert result.execution_verified is True


@pytest.mark.asyncio
async def test_execute_task_needs_human_input(agent_row: dict, intelligence: AgentIntelligence):
    intelligence.react_engine.run = AsyncMock(
        return_value=ReActResult(
            status=ReActStatus.NEEDS_HUMAN_INPUT,
            answer="Which pipeline stage?",
            iterations=1,
        )
    )
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    with patch("app.operators.agent_intelligence.write_audit_event"):
        with patch("app.operators.agent_intelligence.load_agent_task_history", return_value=[]):
            result = await intelligence.execute_task(
                org_id="org-1",
                agent=agent_row,
                task="Move deal",
                client=client,
            )
    assert result.needs_human_input is True
    assert result.confidence == 35


def test_load_org_context(monkeypatch: pytest.MonkeyPatch):
    client = MagicMock()
    mock_service = MagicMock()
    mock_service.get_snapshot.return_value = {
        "orgId": "org-1",
        "orgName": "Acme Corp",
        "connectedIntegrations": ["hubspot"],
        "connectorCount": 1,
    }
    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_org_context_service",
        lambda: mock_service,
    )
    ctx = load_org_context(client, "org-1")
    assert ctx["orgName"] == "Acme Corp"
    assert ctx["connectedIntegrations"] == ["hubspot"]
    mock_service.get_snapshot.assert_called_once()


def test_select_model_for_agent_uses_agent_model(agent_row: dict):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    with patch(
        "app.operators.agent_intelligence.resolve_agent_inference_model",
        return_value=SimpleNamespace(
            fine_tuned_openai_id=None,
            base_model="gpt-4.1-mini",
        ),
    ):
        model = select_model_for_agent(agent_row, client, "org-1", "short task")
    assert model == "gpt-5.5"


def test_select_model_for_agent_complexity_hint():
    client = MagicMock()
    with patch(
        "app.operators.agent_intelligence.resolve_agent_inference_model",
        return_value=SimpleNamespace(fine_tuned_openai_id=None, base_model=None),
    ):
        model = select_model_for_agent(
            {"model": None},
            client,
            "org-1",
            "short",
            parameters={"complexity": "high"},
        )
    assert model == "gpt-5.5"


def test_load_agent_task_history_filters_by_agent():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "job-old",
                "payload": {"agent_id": "agent-1", "task": "Prior task"},
                "result": {"summary": "Prior result"},
                "finished_at": "2026-06-01T00:00:00Z",
                "status": "completed",
            },
            {
                "id": "job-other",
                "payload": {"agent_id": "agent-2", "task": "Other agent"},
                "result": {"summary": "Skip"},
                "finished_at": "2026-06-02T00:00:00Z",
                "status": "completed",
            },
        ]
    )
    history = load_agent_task_history(client, "org-1", "agent-1", exclude_task_id="job-current")
    assert len(history) == 1
    assert history[0]["task"] == "Prior task"
    assert history[0]["summary"] == "Prior result"


def test_build_task_prompt_includes_task_history():
    prompt = AgentIntelligence._build_task_prompt(
        "Do thing",
        briefing={"dealId": "d1"},
        parameters={},
        org_context={"orgName": "Acme"},
        rag_section="",
        memory_section="",
        task_history=[{"task": "Old task", "summary": "Old summary"}],
    )
    assert "<task_history>" in prompt
    assert "Old task" in prompt
    assert "<handoff_briefing>" in prompt


@pytest.mark.asyncio
async def test_execute_task_includes_task_history(agent_row: dict, intelligence: AgentIntelligence):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    history_rows = MagicMock(
        data=[
            {
                "id": "job-prior",
                "payload": {"agent_id": "agent-1", "task": "Earlier work"},
                "result": {"summary": "Done earlier"},
                "finished_at": "2026-06-01T00:00:00Z",
                "status": "completed",
            }
        ]
    )
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = history_rows

    with patch("app.operators.agent_intelligence.write_audit_event"):
        await intelligence.execute_task(
            org_id="org-1",
            agent=agent_row,
            task="Follow up",
            client=client,
            task_id="job-current",
        )
    task_prompt = intelligence.react_engine.run.await_args.kwargs["task"]
    assert "<task_history>" in task_prompt
    assert "Earlier work" in task_prompt


def test_build_agent_system_prompt_includes_role():
    prompt = build_agent_system_prompt(
        {"name": "CS Bot", "role": "CS", "systems": ["zendesk"]},
        org_context={"orgName": "Acme"},
        connected_integrations=["zendesk"],
        rag_available=False,
    )
    assert "customer success" in prompt.lower()
    assert "Acme" in prompt
    assert "zendesk" in prompt.lower()


def test_normalize_agent_role_aliases():
    assert normalize_agent_role("Customer Success") == "CS"
    assert normalize_agent_role("revops") == "REVENUE_OPS"


def test_agent_result_to_handoff_dict():
    result = AgentResult(
        summary="Done",
        answer="Done",
        agent_id="a1",
        agent_name="Agent",
        task="t",
        confidence=80,
        recommended_actions=["Executed hubspot_search_contacts"],
    )
    payload = result.to_handoff_dict()
    assert payload["summary"] == "Done"
    assert payload["confidence"] == 80


def test_build_system_prompt_adds_spoken_register(intelligence: AgentIntelligence):
    prompt = intelligence._build_system_prompt(
        "assistant",
        None,
        [],
        {"orgName": "Acme"},
        spoken_mode=True,
    )
    assert "Register 5 — SPOKEN" in prompt


@pytest.mark.asyncio
async def test_streaming_emits_text_events_when_react_returns_answer_only(intelligence: AgentIntelligence):
    """ReAct may finish with answer text but no text_delta chunks; SSE contract still requires text-* events."""
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )

    async def fake_streaming(**kwargs):
        yield SimpleNamespace(
            kind="done",
            react_result=ReActResult(status=ReActStatus.COMPLETED, answer="smoke-ok"),
        )

    intelligence.react_engine.run_streaming = fake_streaming
    orchestrator = MagicMock()
    orchestrator.get_context_for_prompt = AsyncMock(return_value="")

    events: list[object] = []
    with patch("app.services.mcp_client_service.get_mcp_client_service") as mcp_svc:
        mcp_svc.return_value.get_enabled_tools_for_org = AsyncMock(return_value=[])
        with patch("app.operators.agent_intelligence.get_company_intelligence_orchestrator", return_value=orchestrator):
            with patch("app.operators.agent_intelligence.build_entity_context_section", AsyncMock(return_value="")):
                with patch("app.operators.agent_intelligence.get_org_context_service") as org_service:
                    org_service.return_value.get_context_bundle.return_value = (
                        {"orgName": "Acme", "connectedIntegrations": ["hubspot"]},
                        "Org block",
                    )
                    with patch(
                        "app.operators.agent_intelligence.maybe_summarize_history",
                        AsyncMock(return_value=SimpleNamespace(messages=[], summary=None, summary_updated=False)),
                    ):
                        with patch_agent_streaming_dialogue_pipeline():
                            async for event in intelligence.execute_task_streaming(
                                org_id="org-1",
                                user_id="user-1",
                                query="Say smoke-ok in one word.",
                                mode="standard",
                                requested_tools=["agent_status"],
                                client=client,
                            ):
                                events.append(event)

    sse_types = [event.sse_type for event in events if isinstance(event, AssistantStreamEvent)]
    assert "text-start" in sse_types
    assert "text-delta" in sse_types
    assert "text-end" in sse_types
    complete = next(event for event in events if isinstance(event, AssistantStreamComplete))
    assert complete.full_content == "smoke-ok"


@pytest.mark.asyncio
async def test_spoken_mode_skips_tier0_cache(intelligence: AgentIntelligence):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        MagicMock(data=[])
    )

    async def fake_streaming(**kwargs):
        yield SimpleNamespace(
            kind="done",
            react_result=ReActResult(status=ReActStatus.COMPLETED, answer="spoken-path-ok"),
        )

    intelligence.react_engine.run_streaming = fake_streaming
    orchestrator = MagicMock()
    orchestrator.get_context_for_prompt = AsyncMock(return_value="")
    tier0_hit = {
        "answer": "Tier0 cache should not be used for spoken turns.",
        "confidence": {"score": 1.0, "needs_clarification": False},
        "answer_explanation": "cached",
    }

    events: list[object] = []
    with patch(
        "app.operators.agent_intelligence.get_tier0_answer",
        AsyncMock(return_value=tier0_hit),
    ) as mock_tier0:
        with patch("app.operators.agent_intelligence.tier0_enabled", return_value=True):
            with patch("app.services.mcp_client_service.get_mcp_client_service") as mcp_svc:
                mcp_svc.return_value.get_enabled_tools_for_org = AsyncMock(return_value=[])
                with patch(
                    "app.operators.agent_intelligence.get_company_intelligence_orchestrator",
                    return_value=orchestrator,
                ):
                    with patch(
                        "app.operators.agent_intelligence.build_entity_context_section",
                        AsyncMock(return_value=""),
                    ):
                        with patch("app.operators.agent_intelligence.get_org_context_service") as org_service:
                            org_service.return_value.get_context_bundle.return_value = (
                                {"orgName": "Acme", "connectedIntegrations": ["hubspot"]},
                                "Org block",
                            )
                            with patch(
                                "app.operators.agent_intelligence.maybe_summarize_history",
                                AsyncMock(
                                    return_value=SimpleNamespace(
                                        messages=[],
                                        summary=None,
                                        summary_updated=False,
                                    )
                                ),
                            ):
                                with patch_agent_streaming_dialogue_pipeline():
                                    async for event in intelligence.execute_task_streaming(
                                        org_id="org-1",
                                        user_id="user-1",
                                        query="Say spoken-path-ok in one sentence.",
                                        mode="fast",
                                        requested_tools=["agent_status"],
                                        client=client,
                                        spoken_mode=True,
                                    ):
                                        events.append(event)

    mock_tier0.assert_not_awaited()
    complete = next(event for event in events if isinstance(event, AssistantStreamComplete))
    assert complete.model != "cache"
    assert complete.full_content == "spoken-path-ok"


@pytest.mark.asyncio
async def test_run_agent_task_delegates_to_intelligence():
    from app.services.handoff_service import run_agent_task

    settings = SimpleNamespace()
    agent = {"id": "a1", "name": "Agent", "systems": []}
    mock_result = AgentResult(summary="ok", answer="ok", agent_id="a1", agent_name="Agent", task="t", confidence=70)
    with patch(
        "app.operators.agent_intelligence.get_agent_intelligence"
    ) as mock_get:
        mock_get.return_value.execute_task = AsyncMock(return_value=mock_result)
        with patch("app.services.handoff_service.get_supabase_client", return_value=MagicMock()):
            output = await run_agent_task(
                settings,
                org_id="org-1",
                agent=agent,
                task="Do thing",
                actor_id="user-1",
            )
    assert output["summary"] == "ok"
    assert output["agent_id"] == "a1"

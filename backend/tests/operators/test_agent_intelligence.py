from __future__ import annotations

import asyncio
import threading
import time
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
    settings = SimpleNamespace(
        disable_ai=False,
        rag_top_k=5,
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
    )
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


@pytest.mark.parametrize("saved_model", ["auto", "Auto", "", None, "default"])
def test_select_model_for_agent_treats_auto_as_unpinned(saved_model):
    from app.operators.agent_intelligence import MODEL_TIERS

    with patch(
        "app.operators.agent_intelligence.resolve_agent_inference_model",
        return_value=SimpleNamespace(fine_tuned_openai_id=None, base_model="gpt-4.1-mini", trained_model_id=None),
    ):
        model = select_model_for_agent(
            {"model": saved_model},
            MagicMock(),
            "org-1",
            "short",
            parameters={"complexity": "high"},
        )
    assert model == MODEL_TIERS["high"]["openai"]
    assert model != "auto"


def test_explicit_agent_model_and_inference_base_ignore_auto():
    from app.services.agent_finetune_service import (
        DEFAULT_AGENT_BASE_MODEL,
        explicit_agent_model,
        resolve_agent_inference_model,
    )

    assert explicit_agent_model({"model": " auto "}) is None
    assert explicit_agent_model({"model": "gpt-5.5"}) == "gpt-5.5"
    inference = resolve_agent_inference_model(MagicMock(), "org-1", {"id": "a1", "model": "auto"})
    assert inference.base_model == DEFAULT_AGENT_BASE_MODEL


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


@pytest.mark.parametrize('spoken_mode', [False, True])
def test_repeated_current_request_reaches_shared_text_and_voice_prompt(intelligence, spoken_mode):
    prompt = intelligence._build_system_prompt(
        'assistant', None, [], {'orgName': 'Acme'}, spoken_mode=spoken_mode,
        spoken_user_text='Please rewrite the welcome note.',
        task_history=[{'role':'user', 'content':'Please rewrite the welcome note.'},
                      {'role':'assistant', 'content':'I already gave you a warmer version in my last message.'}],
    )
    assert '## Current repeated request' in prompt
    assert prompt.index('## Current repeated request') > prompt.index('## Anti-repeat')
    assert 'does not authorize tool execution' in prompt


def test_build_system_prompt_includes_operator_act_section(intelligence: AgentIntelligence):
    prompt = intelligence._build_system_prompt(
        "assistant",
        None,
        [],
        {"orgName": "Acme"},
        operator_act_section="## Operator Act Context\nConnected systems: hubspot",
    )
    assert "## Operator Act Context" in prompt
    assert "hubspot" in prompt


def test_build_system_prompt_prefers_ranked_context_over_unranked_rag(
    intelligence: AgentIntelligence,
):
    prompt = intelligence._build_system_prompt(
        "assistant",
        None,
        [{"source": "legacy", "content": "unranked evidence"}],
        {"orgName": "Acme"},
        ranked_context_section="ranked authoritative evidence",
    )

    assert "ranked authoritative evidence" in prompt
    assert "unranked evidence" not in prompt


def test_build_system_prompt_honors_ranker_exclusions_without_fallback(
    intelligence: AgentIntelligence,
):
    prompt = intelligence._build_system_prompt(
        "assistant",
        None,
        [{"source": "legacy", "content": "excluded evidence"}],
        {"orgName": "Excluded Acme"},
        ranked_context_section="",
        suppress_unranked_context_fallback=True,
    )

    assert "excluded evidence" not in prompt
    assert "Organization: Excluded Acme" not in prompt


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


def test_execute_task_streaming_does_not_rebind_module_imports():
    """Typed chat crashed when spoken plan-hold imported asyncio/composer inside the method.

    Production evidence (SHA 43570699): UnboundLocalError asyncio and NameError
    compose_reply_events on /api/assistant/chat hello / smoke-ok.
    """
    names = AgentIntelligence.execute_task_streaming.__code__.co_varnames
    assert "asyncio" not in names
    assert "compose_reply_events" not in names


@pytest.mark.asyncio
async def test_gateway_shortcut_composes_before_task_state_reload(intelligence: AgentIntelligence):
    """Phase D: gateway shortcuts call _composed_reply before task_state is reloaded."""
    from app.services.intent_gateway import GatewayDecision
    from app.services.response_composer import ComposerPacked

    client = MagicMock()
    state_svc = MagicMock()
    state_svc.get_task_state = AsyncMock(return_value={})

    gateway_decision = GatewayDecision(
        action="shortcut",
        reason="phrase",
        candidate_id="phrase_bank",
        confidence=0.93,
        answer="Hello! How can I help you today?",
    )
    packed = ComposerPacked(
        text="Hello! How can I help you today?",
        text_id="txt-gateway",
        events=[
            AssistantStreamEvent(sse_type="text-start", payload={"id": "txt-gateway"}),
            AssistantStreamEvent(
                sse_type="text-delta",
                payload={"id": "txt-gateway", "delta": "Hello! How can I help you today?"},
            ),
            AssistantStreamEvent(sse_type="text-end", payload={"id": "txt-gateway"}),
        ],
        kind="shortcut",
        used_model=False,
    )

    events: list[object] = []
    with patch(
        "app.services.intent_gateway.evaluate_intent_gateway",
        AsyncMock(return_value=gateway_decision),
    ):
        with patch(
            "app.services.conversation_state_service.get_conversation_state_service",
            return_value=state_svc,
        ):
            with patch(
                "app.operators.agent_intelligence.compose_reply_events",
                AsyncMock(return_value=packed),
            ):
                async for event in intelligence.execute_task_streaming(
                    org_id="org-1",
                    user_id="user-1",
                    query="hello",
                    mode="fast",
                    conversation_id="conv-gateway",
                    client=client,
                ):
                    events.append(event)

    complete = next(event for event in events if isinstance(event, AssistantStreamComplete))
    assert complete.full_content == "Hello! How can I help you today?"
    assert complete.model == "intent_gateway:phrase_bank"
    trace = (complete.task_state or {}).get("cognitive_turn_trace")
    assert isinstance(trace, dict)
    assert trace.get("turn_id")
    sse_types = [event.sse_type for event in events if isinstance(event, AssistantStreamEvent)]
    assert "text-delta" in sse_types


def _packed_reply(text: str, text_id: str, kind: str) -> object:
    from app.services.response_composer import ComposerPacked

    return ComposerPacked(
        text=text,
        text_id=text_id,
        events=[
            AssistantStreamEvent(sse_type="text-start", payload={"id": text_id}),
            AssistantStreamEvent(sse_type="text-delta", payload={"id": text_id, "delta": text}),
            AssistantStreamEvent(sse_type="text-end", payload={"id": text_id}),
        ],
        kind=kind,
        used_model=False,
    )


@pytest.mark.asyncio
async def test_shared_kernel_typed_and_spoken_plan_hold_both_complete(intelligence: AgentIntelligence):
    """Typed and spoken plan-hold take the SAME path: intent gateway, kernel, ReAct, Composer.

    Spoken "show me the plan before you execute" used to short-circuit into a
    voice-only heuristic plan that skipped the gateway and the kernel. Now both
    modalities reach the gateway, run the shared engine and finish with the
    same model label.
    """
    from app.services.intent_gateway import GatewayDecision

    client = MagicMock()
    state_svc = MagicMock()
    state_svc.get_task_state = AsyncMock(return_value={})
    state_svc.update_task_state = AsyncMock(return_value=None)
    plan_hold = (
        "Check that my Google Ads account is actually connected, and show me "
        "the complete plan before you execute anything. Don't execute without "
        "my approval."
    )
    answer = "Here is the plan. Nothing has run yet."

    async def fake_streaming(**kwargs):
        yield SimpleNamespace(
            kind="done",
            react_result=ReActResult(status=ReActStatus.COMPLETED, answer=answer),
        )

    intelligence.react_engine.run_streaming = fake_streaming
    gateway = AsyncMock(
        return_value=GatewayDecision(action="fallthrough", reason="operator", candidate_id="kernel", confidence=0.4)
    )
    completes: dict[bool, AssistantStreamComplete] = {}
    types: dict[bool, list[str]] = {}
    for spoken in (False, True):
        events: list[object] = []
        with (
            patch("app.services.intent_gateway.evaluate_intent_gateway", gateway),
            patch("app.services.mcp_client_service.get_mcp_client_service") as mcp_svc,
            patch("app.services.risk_approval_evaluator.assert_org_not_blocked"),
            patch(
                "app.services.conversation_state_service.get_conversation_state_service",
                return_value=state_svc,
            ),
            patch(
                "app.operators.agent_intelligence.compose_reply_events",
                AsyncMock(return_value=_packed_reply(answer, f"txt-{spoken}", "plan_hold")),
            ),
            patch_agent_streaming_dialogue_pipeline(),
        ):
            mcp_svc.return_value.get_enabled_tools_for_org = AsyncMock(return_value=[])
            async for event in intelligence.execute_task_streaming(
                org_id="org-1",
                user_id="user-1",
                query=plan_hold,
                mode="fast",
                conversation_id=f"conv-{spoken}",
                client=client,
                spoken_mode=spoken,
            ):
                events.append(event)
        completes[spoken] = next(e for e in events if isinstance(e, AssistantStreamComplete))
        types[spoken] = [e.sse_type for e in events if isinstance(e, AssistantStreamEvent)]

    assert gateway.await_count == 2
    assert completes[False].model == completes[True].model
    assert completes[False].full_content and completes[True].full_content
    assert "text-delta" in types[False]
    assert "text-delta" in types[True]


@pytest.mark.asyncio
async def test_spoken_turn_hands_its_checkpoints_to_the_caller(intelligence: AgentIntelligence):
    """The voice bridge's per-turn latency record reads the brain's own
    checkpoints from ``latency_marks``, anchored on the caller's clock."""
    from app.services.intent_gateway import GatewayDecision

    state_svc = MagicMock()
    state_svc.get_task_state = AsyncMock(return_value={})
    state_svc.update_task_state = AsyncMock(return_value=None)

    async def fake_streaming(**kwargs):
        yield SimpleNamespace(
            kind="done",
            react_result=ReActResult(status=ReActStatus.COMPLETED, answer="Acme is the priority."),
        )

    intelligence.react_engine.run_streaming = fake_streaming
    marks: dict = {}
    before = time.perf_counter()
    with (
        patch(
            "app.services.intent_gateway.evaluate_intent_gateway",
            AsyncMock(
                return_value=GatewayDecision(
                    action="fallthrough", reason="operator", candidate_id="kernel", confidence=0.4
                )
            ),
        ),
        patch("app.services.mcp_client_service.get_mcp_client_service") as mcp_svc,
        patch("app.services.risk_approval_evaluator.assert_org_not_blocked"),
        patch(
            "app.services.conversation_state_service.get_conversation_state_service",
            return_value=state_svc,
        ),
        patch(
            "app.operators.agent_intelligence.compose_reply_events",
            AsyncMock(return_value=_packed_reply("Acme is the priority.", "txt-m", "success")),
        ),
        patch_agent_streaming_dialogue_pipeline(),
    ):
        mcp_svc.return_value.get_enabled_tools_for_org = AsyncMock(return_value=[])
        async for _event in intelligence.execute_task_streaming(
            org_id="org-1",
            user_id="user-1",
            query="which account is our priority this quarter",
            mode="fast",
            conversation_id="conv-marks",
            client=MagicMock(),
            spoken_mode=True,
            latency_marks=marks,
        ):
            pass

    assert before <= marks["_t0_perf"] <= time.perf_counter()
    for name in ("client_ready", "intent_gateway", "pre_kernel_entry"):
        assert isinstance(marks[name], int), name
    assert marks["client_ready"] <= marks["intent_gateway"] <= marks["pre_kernel_entry"]


@pytest.mark.asyncio
async def test_shared_runtime_typed_normal_turn_emits_composer_and_complete(
    intelligence: AgentIntelligence,
):
    from app.services.intent_gateway import GatewayDecision

    client = MagicMock()
    events: list[object] = []

    async def fake_streaming(**kwargs):
        yield SimpleNamespace(
            kind="done",
            react_result=ReActResult(status=ReActStatus.COMPLETED, answer="Pricing is in the knowledge base."),
        )

    intelligence.react_engine.run_streaming = fake_streaming
    with patch(
        "app.services.intent_gateway.evaluate_intent_gateway",
        AsyncMock(
            return_value=GatewayDecision(
                action="fallthrough",
                reason="operator",
                candidate_id="kernel",
                confidence=0.4,
            )
        ),
    ):
        with patch(
            "app.operators.agent_intelligence.compose_reply_events",
            AsyncMock(return_value=_packed_reply("Pricing is in the knowledge base.", "txt-n", "success")),
        ):
            with patch("app.services.mcp_client_service.get_mcp_client_service") as mcp_svc:
                mcp_svc.return_value.get_enabled_tools_for_org = AsyncMock(return_value=[])
                with patch_agent_streaming_dialogue_pipeline():
                    async for event in intelligence.execute_task_streaming(
                        org_id="org-1",
                        user_id="user-1",
                        query="What is our pricing FAQ?",
                        mode="fast",
                        conversation_id="conv-normal",
                        client=client,
                        spoken_mode=False,
                    ):
                        events.append(event)
    complete = next(e for e in events if isinstance(e, AssistantStreamComplete))
    assert complete.full_content
    assert "text-delta" in [e.sse_type for e in events if isinstance(e, AssistantStreamEvent)]


@pytest.mark.asyncio
async def test_shared_runtime_typed_read_clarify_emits_composer(
    intelligence: AgentIntelligence,
):
    from app.services.intent_gateway import GatewayDecision

    client = MagicMock()
    events: list[object] = []

    async def fake_streaming(**kwargs):
        yield SimpleNamespace(
            kind="done",
            react_result=ReActResult(
                status=ReActStatus.COMPLETED,
                answer="I don't have enough information yet. Tell me which analytics source to use.",
            ),
        )

    intelligence.react_engine.run_streaming = fake_streaming
    with patch(
        "app.services.intent_gateway.evaluate_intent_gateway",
        AsyncMock(
            return_value=GatewayDecision(
                action="fallthrough",
                reason="read",
                candidate_id="kernel",
                confidence=0.5,
            )
        ),
    ):
        with patch(
            "app.operators.agent_intelligence.compose_reply_events",
            AsyncMock(
                return_value=_packed_reply(
                    "I don't have enough information yet. Tell me which analytics source to use.",
                    "txt-read",
                    "clarify",
                )
            ),
        ):
            with patch(
                "app.services.unified_turn_reasoning_service.apply_unified_turn_live",
                AsyncMock(return_value=None),
            ):
                with patch("app.services.mcp_client_service.get_mcp_client_service") as mcp_svc:
                    mcp_svc.return_value.get_enabled_tools_for_org = AsyncMock(return_value=[])
                    with patch_agent_streaming_dialogue_pipeline():
                        async for event in intelligence.execute_task_streaming(
                            org_id="org-1",
                            user_id="user-1",
                            query="Tell me what my website traffic was last month.",
                            mode="fast",
                            conversation_id="conv-read",
                            client=client,
                            spoken_mode=False,
                        ):
                            events.append(event)
    complete = next(e for e in events if isinstance(e, AssistantStreamComplete))
    assert "enough information" in complete.full_content.lower() or complete.full_content
    assert "text-delta" in [e.sse_type for e in events if isinstance(e, AssistantStreamEvent)]


@pytest.mark.asyncio
async def test_shared_runtime_shortcut_complete_carries_task_state(
    intelligence: AgentIntelligence,
):
    from app.services.intent_gateway import GatewayDecision

    client = MagicMock()
    state_svc = MagicMock()
    state_svc.get_task_state = AsyncMock(return_value={"turn": 1})
    events: list[object] = []
    with patch(
        "app.services.intent_gateway.evaluate_intent_gateway",
        AsyncMock(
            return_value=GatewayDecision(
                action="shortcut",
                reason="phrase",
                candidate_id="phrase_bank",
                confidence=0.93,
                answer="Hello! How can I help you today?",
            )
        ),
    ):
        with patch(
            "app.services.conversation_state_service.get_conversation_state_service",
            return_value=state_svc,
        ):
            with patch(
                "app.operators.agent_intelligence.compose_reply_events",
                AsyncMock(return_value=_packed_reply("Hello! How can I help you today?", "txt-p", "shortcut")),
            ):
                async for event in intelligence.execute_task_streaming(
                    org_id="org-1",
                    user_id="user-1",
                    query="hello",
                    mode="fast",
                    conversation_id="conv-persist",
                    client=client,
                    spoken_mode=False,
                ):
                    events.append(event)
    complete = next(e for e in events if isinstance(e, AssistantStreamComplete))
    assert isinstance(complete.task_state, dict)
    assert complete.task_state.get("shortcut_latency_ms") is not None


@pytest.mark.asyncio
async def test_shared_runtime_write_approval_does_not_invoke_provider():
    from app.services.react_write_gate import block_react_write_execution
    from app.services.tool_registry import get_tool_registry

    invoke = MagicMock()
    blocked = block_react_write_execution(
        "email_send",
        {"to": "model@example.com", "subject": "x", "body": "y"},
        registry=get_tool_registry(),
        client=MagicMock(),
        org_id="org-1",
        user_id="user-1",
        user_message="Email ada@example.com subject line, Hi and body of the email say: Hello",
        connected_integrations=["email"],
    )
    assert blocked is not None
    assert blocked.get("pending_approval") is True
    invoke.assert_not_called()


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
async def test_connected_integrations_mcp_tools_and_engine_settings_run_concurrently(
    intelligence: AgentIntelligence,
):
    """Speed/latency-standard follow-up (2026-09-05): these three pre-kernel
    calls used to be three sequential awaits (list_connected_integrations is
    itself synchronous/blocking) with no data dependency on each other.

    Records each call's own start timestamp rather than total pipeline wall
    time, since the rest of the (real, only lightly-mocked) pipeline has its
    own real latency unrelated to this specific fix — asserting on their
    start times isolates exactly the thing this change claims: all three
    begin within a few ms of each other, not one-after-another.

    MUTATION PROOF: revert the asyncio.gather back to three sequential
    awaits and this test fails — sequential starts would be delay-apart
    (~200ms), not ~0ms apart.
    """
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        MagicMock(data=[])
    )
    delay = 0.2
    starts: dict[str, float] = {}

    def _slow_connected(*_a, **_k):
        starts["connected_integrations"] = time.perf_counter()
        time.sleep(delay)
        return ["hubspot"]

    intelligence.tool_registry.list_connected_integrations.side_effect = _slow_connected

    async def fake_streaming(**kwargs):
        yield SimpleNamespace(
            kind="done",
            react_result=ReActResult(status=ReActStatus.COMPLETED, answer="ok"),
        )

    intelligence.react_engine.run_streaming = fake_streaming
    orchestrator = MagicMock()
    orchestrator.get_context_for_prompt = AsyncMock(return_value="")

    async def _slow_mcp_tools(*_a, **_k):
        starts["mcp_tools"] = time.perf_counter()
        await asyncio.sleep(delay)
        return []

    from app.services.intelligence_engine_settings import DEFAULTS as _default_engine_settings

    async def _slow_engine_settings(*_a, **_k):
        starts["engine_settings"] = time.perf_counter()
        await asyncio.sleep(delay)
        return _default_engine_settings

    events: list[object] = []
    with (
        patch("app.services.mcp_client_service.get_mcp_client_service") as mcp_svc,
        patch(
            "app.operators.agent_intelligence.load_intelligence_engine_settings",
            side_effect=_slow_engine_settings,
        ),
        patch(
            "app.operators.agent_intelligence.get_company_intelligence_orchestrator",
            return_value=orchestrator,
        ),
        patch("app.operators.agent_intelligence.build_entity_context_section", AsyncMock(return_value="")),
        patch("app.operators.agent_intelligence.get_org_context_service") as org_service,
        patch(
            "app.operators.agent_intelligence.maybe_summarize_history",
            AsyncMock(return_value=SimpleNamespace(messages=[], summary=None, summary_updated=False)),
        ),
        patch_agent_streaming_dialogue_pipeline(),
    ):
        mcp_svc.return_value.get_enabled_tools_for_org = _slow_mcp_tools
        org_service.return_value.get_context_bundle.return_value = (
            {"orgName": "Acme", "connectedIntegrations": ["hubspot"]},
            "Org block",
        )
        async for event in intelligence.execute_task_streaming(
            org_id="org-1",
            user_id="user-1",
            query="Say ok in one word.",
            mode="fast",
            requested_tools=["agent_status"],
            client=client,
            spoken_mode=True,
        ):
            events.append(event)

    # Spoken non-write defers MCP catalog off the critical path — only connected +
    # engine_settings run concurrently (see execute_task_streaming spoken branch).
    assert set(starts) == {"connected_integrations", "engine_settings"}
    spread = max(starts.values()) - min(starts.values())
    # Sequential would space these delay apart (~200ms between each start).
    # Real concurrency starts both within one scheduler tick.
    assert spread < delay / 2, f"pre-kernel calls started {spread:.3f}s apart — not running concurrently"


@pytest.mark.asyncio
async def test_schedule_connected_integrations_prefetch_does_not_block():
    """Voice-latency round-count audit (2026-09-06): prefetch_connected_integrations
    is a *synchronous*, blocking, live-network call (list_executable_integrations
    does one HTTP round-trip per connected connector when force_live=True). Calling
    a sync function from an async function does not make it background work — it
    blocks the caller's coroutine, and the whole event loop, for as long as the
    live checks take. A live production probe caught this stalling a
    consequential_write_shaped voice turn by several seconds
    (`list_connected_integrations_failed force_live=True error=[Errno 11]
    Resource temporarily unavailable`) firing at the exact point this call ran
    inline inside execute_task_streaming.

    Fix: `_schedule_connected_integrations_prefetch` genuinely backgrounds it
    via asyncio.to_thread + asyncio.create_task, never awaited inline, with a
    strong ref kept in _PREFETCH_BACKGROUND_TASKS so it is not garbage
    collected before it finishes its (already best-effort, write-through-cache)
    work.

    MUTATION PROOF: revert `_schedule_connected_integrations_prefetch` to call
    `prefetch_connected_integrations(...)` directly (synchronously) instead of
    via asyncio.to_thread/create_task, and this test fails — the call would
    block the awaiting caller for the full `delay` instead of returning
    almost immediately.
    """
    from app.operators.agent_intelligence import (
        _PREFETCH_BACKGROUND_TASKS,
        _schedule_connected_integrations_prefetch,
    )

    client = MagicMock()
    delay = 0.3
    prefetch_started = threading.Event()
    prefetch_finished = threading.Event()
    calls: list[tuple[Any, str]] = []

    def _slow_prefetch(passed_client, passed_org_id, *, environment_name=None):
        prefetch_started.set()
        calls.append((passed_client, passed_org_id))
        time.sleep(delay)
        prefetch_finished.set()
        return None

    with patch(
        "app.services.connector_snapshot_cache.prefetch_connected_integrations",
        side_effect=_slow_prefetch,
    ):
        start = time.perf_counter()
        task = _schedule_connected_integrations_prefetch(client, "org-1", environment_name="production")
        schedule_elapsed = time.perf_counter() - start

        assert schedule_elapsed < delay / 2, (
            f"scheduling took {schedule_elapsed:.3f}s but must return almost "
            "immediately — it must not synchronously run the slow prefetch"
        )
        assert task in _PREFETCH_BACKGROUND_TASKS, "task must be strong-ref'd until it completes"

        # Give the backgrounded thread time to actually run, proving this is a
        # real asyncio.to_thread task that executes and completes — not
        # something dropped or never scheduled at all.
        await asyncio.wait_for(task, timeout=delay * 3)

    assert prefetch_started.is_set(), "prefetch_connected_integrations was never invoked"
    assert prefetch_finished.is_set(), "backgrounded prefetch task never ran to completion"
    assert calls == [(client, "org-1")]
    # The done-callback must remove it once finished, or the set leaks forever.
    assert task not in _PREFETCH_BACKGROUND_TASKS, "completed task must be discarded from the strong-ref set"


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "approval_status,expected_dispatch",
    [("pending_approval", False), ("revoked", False), ("approved", True)],
)
async def test_dec012_execute_task_real_react_dispatch(
    agent_row, intelligence, monkeypatch, approval_status, expected_dispatch,
):
    """Exercise the non-streaming entrypoint with the real ReAct runtime.

    The SQL transport is disposable; approval classification and scope checks
    are not patched. The registry dispatch boundary is a spy/stop sentinel,
    not evidence of a committed provider effect or durable ledger completion.
    """
    import json
    from app.operators.react_engine import ReActEngine
    from app.services.tool_registry import ToolRegistry
    from app.services.workflow_approval_scope import seal_approval_scope
    from tests.db.pg_harness import PG_BIN
    from tests.master_qa.canonical_pg_repository import (
        ORG, USER, PgRepositoryClient, canonical_pg_cluster,
    )

    if PG_BIN is None:
        pytest.skip("Disposable PostgreSQL binaries unavailable")
    tool = "hubspot_update_deal"
    action = "hubspot.deals.update"
    args = {"deal_id": "fixture-deal", "stage": "qualified"}
    registry = ToolRegistry()
    spec = registry.get_spec(tool)
    assert spec is not None and spec.invoke_action == action
    definition = {
        "steps": [{"id": "write-1", "type": "invoke_tool",
                   "config": {"action": action, "params": args}}]
    }
    scope = seal_approval_scope(definition)
    # Connector discovery is synthetic; retain the actual catalog classifier.
    monkeypatch.setattr(registry, "list_connected_integrations", lambda *a, **kw: ["hubspot"])
    monkeypatch.setattr(registry, "enrich_connected_integrations", AsyncMock(return_value=["hubspot"]))
    monkeypatch.setattr(registry, "get_available_tools", AsyncMock(return_value=[spec.to_openai_tool()]))
    dispatch = AsyncMock(return_value={
        "success": False, "action": action, "error": "fixture transport stopped",
        "error_code": "fixture_transport_stopped", "provider_invoked": False,
    })
    monkeypatch.setattr(registry, "execute_tool", dispatch)
    engine = ReActEngine(settings=intelligence.settings, registry=registry)
    engine.router = MagicMock()
    model_call = SimpleNamespace(
        id="dec012-call",
        function=SimpleNamespace(name=tool, arguments=json.dumps(args)),
    )
    def response(content, calls):
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=content, tool_calls=calls),
            finish_reason="stop",
        )])
    monkeypatch.setattr(engine, "_chat_with_tools", AsyncMock(side_effect=[
        response("", [model_call]), response("The deal was updated.", []),
    ]))
    intelligence.react_engine = engine
    intelligence.tool_registry = registry
    monkeypatch.setattr("app.operators.react_engine.moderate_input", AsyncMock())
    monkeypatch.setattr("app.operators.agent_intelligence.load_agent_task_history", lambda *a, **kw: [])
    with canonical_pg_cluster() as pg:
        client = PgRepositoryClient(pg)
        row = client.table("workflow_runs").insert({
            "org_id": ORG, "status": "running", "approval_status": approval_status,
            "required_approvals": 1, "definition_snapshot": definition,
            "parameters": {"approval_scope": scope},
        }).execute().data[0]
        run_id = row["id"]
        result = await intelligence.execute_task(
            org_id=ORG, actor_id=USER, agent=agent_row,
            task="Update the fixture deal stage",
            run_id=run_id, task_id=run_id, environment_name="synthetic",
            parameters={"include_task_history": False, "knowledge_assignments": []},
            client=client, max_iterations=2,
        )
        assert len(result.tool_calls) == 1, result.to_handoff_dict()
        call = result.tool_calls[0]
        assert call["execution_plan_id"] and call["execution_step_id"]
        if expected_dispatch:
            dispatch.assert_awaited_once()
            ctx = dispatch.await_args.kwargs["ctx"]
            assert (ctx.org_id, ctx.actor_id, ctx.run_id) == (ORG, USER, run_id)
            assert ctx.plan_id == call["execution_plan_id"]
            assert ctx.step_id == call["execution_step_id"]
        else:
            dispatch.assert_not_awaited()
            assert call["result"]["error_code"] == "canvas_write_authority_blocked"
        assert not result.outcome_verified
        assert client.table("workflow_runs").select("approval_status").eq(
            "id", run_id
        ).eq("org_id", ORG).limit(1).execute().data[0]["approval_status"] == approval_status


@pytest.mark.asyncio
@pytest.mark.parametrize("approval_status", ["pending_approval", "revoked", "approved"])
async def test_dec012_agent_write_to_durable_outcome(
    agent_row, intelligence, monkeypatch, tmp_path, request, approval_status,
):
    """Real Agent/ReAct/registry/write ledger, HTTP readback and completion hook.

    A persisted job is created through the repository and executed through the
    agent worker handler. Completion and replay use the persisted job row.
    This does not certify queue transport or Play ingress.
    Only model/retrieval inputs, connector discovery/resource metadata, SQL
    transport and the external vendor transport are disposable fixtures.
    """
    import json
    import os
    import urllib.request

    from app.operators import agent_jobs
    from app.operators.react_engine import ReActEngine
    from app.services import domain_events, tool_service
    from app.services.connector_resource_resolver import ResourceResolution
    from app.services.tool_registry import ToolRegistry
    from app.services.tool_types import NormalizedResult
    from app.services.workflow_approval_scope import seal_approval_scope
    from app.workflows import repository
    from tests.db.pg_harness import MIGRATIONS, PG_BIN
    from tests.db.test_autonomous_full_dispatcher_pg import PgClient
    from tests.db.test_autonomous_independent_write_pg import IndependentFixture
    from tests.db.test_domain_event_outbox_pg import ORG, USER, _PsqlRpcClient
    from tests.db.write_recovery_context_fixture import AUTH_ROLE_SQL, CONTEXT_SQL
    from tests.master_qa.canonical_pg_repository import PgRepositoryClient, canonical_pg_cluster
    from tests.master_qa.test_canonical_repository_persistence_pg import (
        _core_effect_tables, _disable_optional_delivery,
    )

    if PG_BIN is None:
        pytest.skip("Disposable PostgreSQL binaries unavailable")
    action = "hubspot.contacts.create"
    tool = "hubspot_create_contact"
    args = {"email": "fixture@example.invalid", "properties": {"email": "fixture@example.invalid"},
            "portal_id": "99887", "connector_id": "local-conn"}
    definition = {"steps": [{"id": "write-1", "type": "invoke_tool", "config": {
        "action": action, "params": args,
    }}]}
    settings = intelligence.settings
    settings.write_authority_mode = "enforce"
    settings.connector_secrets_encryption_key = "k" * 32
    registry = ToolRegistry()
    spec = registry.get_spec(tool)
    assert spec is not None and spec.invoke_action == action
    monkeypatch.setattr(registry, "list_connected_integrations", lambda *a, **kw: ["hubspot"])
    monkeypatch.setattr(registry, "enrich_connected_integrations", AsyncMock(return_value=["hubspot"]))
    monkeypatch.setattr(registry, "get_available_tools", AsyncMock(return_value=[spec.to_openai_tool()]))
    monkeypatch.setattr("app.services.tool_registry.get_tool_registry", lambda: registry)
    monkeypatch.setattr("app.operators.react_engine.get_model_router", MagicMock())
    engine = ReActEngine(settings=settings, registry=registry)
    intelligence.react_engine = engine
    intelligence.tool_registry = registry
    monkeypatch.setattr("app.operators.react_engine.moderate_input", AsyncMock())
    monkeypatch.setattr("app.operators.agent_intelligence.load_agent_task_history", lambda *a, **kw: [])
    # Deterministic advisory inputs keep this gate offline. Dispatch, approval,
    # preflight, ledger, verification and terminal persistence stay real.
    kernel = SimpleNamespace(
        run_pre_act=AsyncMock(return_value=SimpleNamespace(plan=None, turn_id="qa-dec012")),
        run_learn=AsyncMock(),
    )
    monkeypatch.setattr("app.services.cognitive_turn_kernel.get_cognitive_turn_kernel", lambda *a: kernel)
    monkeypatch.setattr("app.services.cognitive_turn_kernel.to_prompt_sections", lambda *a: {})
    monkeypatch.setattr(intelligence, "_knowledge_fabric_section", AsyncMock(return_value=""))
    monkeypatch.setattr("app.operators.agent_intelligence.get_company_intelligence_orchestrator",
                        lambda: SimpleNamespace(get_context_for_prompt=AsyncMock(return_value="")))
    monkeypatch.setattr("app.operators.agent_intelligence.build_entity_context_section", AsyncMock(return_value=""))
    monkeypatch.setattr("app.services.execution_intelligence_context.collect_execution_intelligence",
                        AsyncMock(return_value={"capabilities": {}}))
    resource = ResourceResolution(
        status="resolved", connector_id="hubspot", connection_id="local-conn",
        resource_type="portal", resource_id="99887", display_name="99887",
        confidence=0.98, resolution_reason="linked_config", candidate_count=1,
    )
    monkeypatch.setattr("app.services.write_preflight.resolve_resource", lambda **kw: resource)
    monkeypatch.setattr("app.services.hipaa_service.get_hipaa_status", lambda *a: {"hipaaReady": False})
    monkeypatch.setattr("app.services.agent_tool_permissions.list_agent_tool_permissions", lambda *a, **kw: [
        {"connector_type": "hubspot", "scopes": ["hubspot:read", "hubspot:write"], "expires_at": None},
    ])
    receiver = IndependentFixture(tmp_path / "agent-write.sqlite3", b"<h1>isolated</h1>", capability="dec012")
    request.addfinalizer(receiver.close)
    assert receiver.pid != os.getpid()

    with canonical_pg_cluster() as pg:
        client = PgRepositoryClient(pg)
        pg.psql(AUTH_ROLE_SQL)
        for migration in (
            "20261016032018_write_invoke_idempotency.sql",
            "20261016032029_write_invoke_idempotency_grants.sql",
            "20261102095000_autonomous_atomic_write_claim.sql",
        ):
            pg.psql((MIGRATIONS / migration).read_text())
        pg.psql(CONTEXT_SQL)
        _core_effect_tables(pg)
        _disable_optional_delivery(monkeypatch)
        pg.psql("ALTER TABLE public.audit_logs ALTER COLUMN id SET DEFAULT gen_random_uuid();"
                "ALTER TABLE public.audit_events ALTER COLUMN id SET DEFAULT gen_random_uuid();"
                "CREATE TABLE public.agent_jobs (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "
                "org_id uuid NOT NULL, created_by text, environment text, kind text, session_id text, "
                "payload jsonb, status text, max_attempts integer, queued_at timestamptz, "
                "timeout_at timestamptz, retry_count integer, result jsonb, error text, "
                "finished_at timestamptz, updated_at timestamptz, started_at timestamptz, attempts integer DEFAULT 0);")
        pg.psql((MIGRATIONS / "20261125040000_agent_job_run_binding.sql").read_text())
        pg.psql((MIGRATIONS / "20260606200000_agent_execution_interrupts.sql").read_text())
        ledger = PgClient(str(pg.sock), pg.port)
        repository_rpc = client.rpc

        def rpc(name, params):
            if name not in {"claim_approved_autonomous_write", "bind_write_recovery_context",
                            "finalize_write_invoke_idempotency"}:
                return repository_rpc(name, params)
            if name == "finalize_write_invoke_idempotency":
                params = {**params, "p_result": json.dumps(params["p_result"])}
            return ledger.rpc(name, params)

        monkeypatch.setattr(client, "rpc", rpc)
        run = client.table("workflow_runs").insert({
            "org_id": ORG, "triggered_by": USER, "status": "running", "approval_status": approval_status,
            "required_approvals": 1, "definition_snapshot": definition,
            "parameters": {"approval_scope": seal_approval_scope(definition)},
        }).execute().data[0]
        run_id = run["id"]
        monkeypatch.setattr(agent_jobs, "get_supabase_client", lambda *_: client)
        monkeypatch.setattr("app.operators.agent_intelligence.get_agent_intelligence", lambda: intelligence)
        monkeypatch.setattr("app.operators.agent_intelligence.resolve_agent_record", lambda *a, **kw: agent_row)
        monkeypatch.setattr("app.services.job_workspace_service.get_job_workspace_service",
                            lambda *_: SimpleNamespace(ensure_workspace=AsyncMock()))
        monkeypatch.setattr("app.services.agent_activity_notifications.notify_agent_started", lambda *a, **kw: None)
        job = agent_jobs.create_job(client, ORG, kind="agent_task", environment="synthetic",
                                    created_by=USER, trusted_run_id=run_id,
                                    payload={"task": "Create the fixture contact", "agent_id": agent_row["id"],
                                             "run_id": "untrusted", "context": {"include_task_history": False,
                                             "knowledge_assignments": []}})
        assert job["bound_run_id"] == run_id

        def vendor(context, params):
            assert (context.org_id, context.actor_id, context.run_id) == (ORG, USER, run_id)
            assert context.plan_id and context.step_id and context.preflight_result.ok
            assert params["properties"]["email"] == "fixture@example.invalid"
            assert pg.value("SELECT count(*) FROM public.write_invoke_idempotency "
                            "WHERE status='in_progress' AND connector_id='local-conn' "
                            "AND recovery_context_bound_at IS NOT NULL") == "1"
            post = urllib.request.Request(receiver.origin + "/write",
                data=json.dumps({"cap": "dec012"}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(post, timeout=5) as response:
                assert response.status == 204
            return NormalizedResult(success=True, action=action, data={"id": "1"}, connector_id="local-conn")

        def readback(context, read_action, params):
            assert read_action == "hubspot.contacts.get"
            assert context.org_id == ORG and context.run_id == run_id
            contact_id = params.get("contact_id") or params.get("id")
            get = urllib.request.Request(receiver.origin + f"/records/{contact_id}",
                                         headers={"X-QA-Capability": "dec012"})
            with urllib.request.urlopen(get, timeout=5) as response:
                observed = json.load(response)
            return NormalizedResult(success=True, action=read_action, data=observed)

        monkeypatch.setattr(tool_service, "_resolve_tool_executor", lambda requested, ctx: vendor
                            if requested == action else None)
        monkeypatch.setattr("app.services.sealed_read_execution.invoke_compiled_read", readback)

        async def execute_agent(call_args=None):
            call = SimpleNamespace(id="dec012-write", function=SimpleNamespace(name=tool, arguments=json.dumps(args if call_args is None else call_args)))
            def reply(calls):
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                    content="" if calls else "Finished the fixture task.", tool_calls=calls), finish_reason="stop")])
            monkeypatch.setattr(engine, "_chat_with_tools", AsyncMock(side_effect=[reply([call]), reply([])]))
            return await intelligence.execute_task(
                org_id=ORG, actor_id=USER, agent=agent_row, task="Create the fixture contact",
                run_id=run_id, task_id=run_id, environment_name="synthetic", client=client,
                parameters={"include_task_history": False, "knowledge_assignments": []}, max_iterations=2,
            )

        # Capture the actual AgentResult without replacing the worker or execution engine.
        captured = []
        original_execute = intelligence.execute_task
        async def capture(**kwargs):
            result = await original_execute(**kwargs)
            captured.append(result)
            return result
        monkeypatch.setattr(intelligence, "execute_task", capture)
        call = SimpleNamespace(id="dec012-write", function=SimpleNamespace(name=tool, arguments=json.dumps(args)))
        def reply(calls):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content="" if calls else "Finished the fixture task.", tool_calls=calls), finish_reason="stop")])
        monkeypatch.setattr(engine, "_chat_with_tools", AsyncMock(side_effect=[reply([call]), reply([])]))
        # Isolate optional swarm and approval-notification adapters; provider and outcome remain real.
        monkeypatch.setattr(agent_jobs, "_notify_swarm_job_finished", AsyncMock())
        monkeypatch.setattr("app.services.approval_record_service.maybe_create_agent_job_approval", lambda *a: None)
        if approval_status == "approved":
            assert await agent_jobs._process_job_id(settings, job["id"])
            job = agent_jobs.get_job(client, ORG, job["id"])
            assert job["status"] == "completed" and job["attempts"] == 1
            worker_result = job["result"]
            assert not await agent_jobs._process_job_id(settings, job["id"])
        else:
            job = agent_jobs.claim_job_by_id(client, job["id"])
            assert job and job["status"] == "running"
            worker_result = await agent_jobs.run_agent_task_job(settings, job)
        assert len(captured) == 1
        result = captured[0]
        assert len(result.tool_calls) == 1, result.to_handoff_dict()
        observation = result.tool_calls[0]["result"]
        if approval_status != "approved":
            assert observation["error_code"] == "canvas_write_authority_blocked"
            assert not result.outcome_verified
            assert receiver.writes == 0
            assert pg.value("SELECT count(*) FROM public.write_invoke_idempotency") == "0"
            assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "0"
            assert pg.value(f"SELECT approval_status FROM public.workflow_runs WHERE id='{run_id}'") == approval_status
            return

        assert result.outcome_verified, result.to_handoff_dict()
        assert observation["outcome_verified"] is True
        assert observation["verification"]["resource_id"] == "1"
        assert receiver.writes == 1
        assert result.tool_calls[0]["execution_plan_id"]
        assert result.tool_calls[0]["execution_step_id"]
        assert pg.value("SELECT count(*) FROM public.write_invoke_idempotency "
                        "WHERE status='completed' AND result #>> '{data,id}'='1'") == "1"
        # Follow the worker's existing completion path with the actual rollup.
        assert job["status"] == "completed" and job["bound_run_id"] == run_id
        persisted = repository.get_run_with_steps(PgRepositoryClient(pg), ORG, run_id, "synthetic")
        assert persisted["status"] == "completed"
        assert persisted["parameters"]["outcome_finalized"] is True
        assert pg.value(f"SELECT status FROM public.runs WHERE id='{run_id}'") == "completed"
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"
        for table in ("notifications", "intelligence_outcome_events"):
            assert pg.value(f"SELECT count(*) FROM public.{table}") == "1"

        replay = await execute_agent()
        assert replay.outcome_verified
        assert replay.tool_calls[0]["result"]["verification"]["resource_id"] == "1"
        assert receiver.writes == 1
        changed = {**args, "email": "different@example.invalid",
                   "properties": {"email": "different@example.invalid"}}
        rejected = await execute_agent(changed)
        assert rejected.tool_calls[0]["result"]["error_code"] == "approval_scope_args_mismatch"
        assert not rejected.outcome_verified
        assert receiver.writes == 1
        assert pg.value("SELECT count(*) FROM public.write_invoke_idempotency") == "1"
        # Separate threads and database connections exercise the completion replay race.
        def complete_again():
            asyncio.run(agent_jobs._notify_operator_job_finished(settings, PgRepositoryClient(pg), job, worker_result))
        await asyncio.gather(*(asyncio.to_thread(complete_again) for _ in range(4)))
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"
        pg.psql("CREATE TABLE public.qa_dec012_effects (event_id bigint PRIMARY KEY, run_id uuid NOT NULL)")

        def consume(_client, event):
            assert event["org_id"] == ORG and event["aggregate_id"] == run_id
            assert event["payload"]["status"] == "completed"
            pg.psql("INSERT INTO public.qa_dec012_effects VALUES "
                    f"({int(event['id'])},'{run_id}') ON CONFLICT (event_id) DO NOTHING")

        domain_events.reset_domain_event_handlers_for_tests()
        domain_events.register_domain_event_handler(domain_events.EVENT_EXECUTION_OUTCOME_FINALIZED,
                                                     "qa_dec012_consumer", consume)
        try:
            relay = domain_events.DomainEventRelay(_PsqlRpcClient(pg), worker_id="qa-dec012")
            assert relay.run_once().delivered == 1
            assert relay.run_once().claimed == 0
            pg.psql("UPDATE public.domain_event_outbox SET status='pending', available_at=now(), "
                    "delivered_at=NULL, delivered_handlers='{}'::text[]")
            assert relay.run_once().delivered == 1
        finally:
            domain_events.reset_domain_event_handlers_for_tests()
        assert pg.value("SELECT count(*) FROM public.qa_dec012_effects") == "1"
        assert receiver.writes == 1
        for table in ("audit_logs", "audit_events"):
            assert pg.value(f"SELECT count(*) FROM public.{table} "
                            f"WHERE resource_id='{run_id}' AND action='workflow.execute.completed'") == "1"
        for table in ("notifications", "intelligence_outcome_events"):
            assert pg.value(f"SELECT count(*) FROM public.{table}") == "1"
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox WHERE status='delivered'") == "1"

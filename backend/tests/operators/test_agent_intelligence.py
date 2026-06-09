from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators.agent_intelligence import (
    AgentIntelligence,
    AgentResult,
    load_org_context,
    select_model_for_agent,
)
from app.operators.agent_prompts import build_agent_system_prompt, normalize_agent_role
from app.operators.react_engine import ReActResult, ReActStatus, ReActTraceStep


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
    intel = AgentIntelligence(settings=settings, react_engine=react, rag_service=rag)
    intel.tool_registry = MagicMock()
    intel.tool_registry.list_connected_integrations.return_value = ["hubspot"]
    return intel


@pytest.mark.asyncio
async def test_execute_task_runs_react_with_context(agent_row: dict, intelligence: AgentIntelligence):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "org-1", "name": "Acme"}]
    )
    with patch("app.operators.agent_intelligence.build_task_retrieval_context", return_value={"memories": []}):
        with patch("app.operators.agent_intelligence.write_audit_event"):
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
    with patch("app.operators.agent_intelligence.build_task_retrieval_context", return_value={}):
        with patch("app.operators.agent_intelligence.write_audit_event"):
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

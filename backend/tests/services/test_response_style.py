"""Response styles: distinct criteria, agent precedence, and injection into every prompt path."""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators.agent_intelligence import AgentIntelligence
from app.operators.react_engine import ReActResult, ReActStatus
from app.services.module_d_unified_voice_spec import build_module_d_unified_system_prompt
from app.services.persona_service import (
    RESPONSE_STYLE_CRITERIA,
    RESPONSE_STYLE_CRITERIA_FIELDS,
    PersonaService,
    agent_response_style_key,
    build_response_style_section,
    resolve_response_style_key,
    response_style_label,
)

ALL_STYLES = sorted(RESPONSE_STYLE_CRITERIA)


# --- catalog + criteria -------------------------------------------------------


def test_style_catalog_matches_persona_catalog():
    assert set(RESPONSE_STYLE_CRITERIA) == set(PersonaService.COMMUNICATION_PERSONAS)
    assert "hr_advisor" in RESPONSE_STYLE_CRITERIA


@pytest.mark.parametrize("key", ALL_STYLES)
def test_every_style_defines_all_criteria(key: str):
    criteria = RESPONSE_STYLE_CRITERIA[key]
    for field in RESPONSE_STYLE_CRITERIA_FIELDS:
        assert str(criteria.get(field) or "").strip(), f"{key} missing {field}"
    assert 1 <= int(criteria["spoken_max_sentences"]) <= 3


@pytest.mark.parametrize("field", RESPONSE_STYLE_CRITERIA_FIELDS)
def test_each_criterion_is_unique_across_styles(field: str):
    values = [RESPONSE_STYLE_CRITERIA[key][field].strip().lower() for key in ALL_STYLES]
    assert len(set(values)) == len(values), f"duplicate {field} across styles"


@pytest.mark.parametrize("spoken", [False, True])
def test_each_style_yields_a_distinct_section(spoken: bool):
    sections = {key: build_response_style_section(key, spoken=spoken) for key in ALL_STYLES}
    assert len(set(sections.values())) == len(sections)
    for key, section in sections.items():
        assert section.startswith(f"## Response style: {response_style_label(key)}")
        criteria = RESPONSE_STYLE_CRITERIA[key]
        assert criteria["tone"] in section
        assert criteria["signature"] in section
        assert criteria["question_style"] in section


def test_written_section_has_length_and_structure_rules():
    section = build_response_style_section("executive_strategist")
    assert "- Length: Very brief" in section
    assert "- Structure: Bottom line first" in section


def test_spoken_section_drops_formatting_and_caps_sentences():
    section = build_response_style_section("deep_research_analyst", spoken=True)
    assert "- Structure:" not in section
    assert "speak at most 3 short sentences" in section
    assert "no lists, headings, or markdown" in section
    assert RESPONSE_STYLE_CRITERIA["deep_research_analyst"]["tone"] in section


def test_unknown_style_falls_back_to_friendly_assistant():
    assert build_response_style_section("nope").startswith("## Response style: Friendly Assistant")


def test_style_never_overrides_safety():
    for key in ALL_STYLES:
        section = build_response_style_section(key).lower()
        assert "safety, honesty, and approval rules still win" in section
        assert "bypass" not in section and "skip approval" not in section


# --- precedence ---------------------------------------------------------------


def test_agent_config_style_beats_requested_style():
    agent = {"id": "a1", "config": {"response_style": "sales_advisor"}}
    assert resolve_response_style_key(agent, "finance_analyst") == "sales_advisor"


def test_agent_preferred_persona_is_fallback_key():
    agent = {"id": "a1", "config": {"preferred_persona": "hr_advisor"}}
    assert agent_response_style_key(agent) == "hr_advisor"


def test_requested_style_used_when_agent_has_none_or_invalid():
    assert resolve_response_style_key({"config": {"response_style": "bogus"}}, "finance_analyst") == "finance_analyst"
    assert resolve_response_style_key(None, "engineering_copilot") == "engineering_copilot"
    assert resolve_response_style_key(None, None) == "friendly_assistant"


def test_persona_for_key_sets_persona_key():
    persona = PersonaService().persona_for_key("operations_analyst")
    assert persona["persona_key"] == "operations_analyst"
    assert PersonaService().persona_for_key("bogus")["persona_key"] == "friendly_assistant"


# --- classical prompt builder -------------------------------------------------


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
    react.run = AsyncMock(return_value=ReActResult(status=ReActStatus.COMPLETED, answer="done", iterations=1))
    unified = MagicMock()
    unified.retrieve = AsyncMock(
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
    intel = AgentIntelligence(settings=settings, react_engine=react, rag_service=MagicMock(), unified_retrieval=unified)
    intel.tool_registry = MagicMock()
    intel.tool_registry.list_connected_integrations.return_value = []
    intel.tool_registry.enrich_connected_integrations = AsyncMock(
        side_effect=lambda _client, _org_id, connected: connected
    )
    intel.tool_registry.get_available_tools = AsyncMock(return_value=[])
    intel.tool_registry.get_tools_for_agent.return_value = []
    return intel


def test_build_system_prompt_uses_requested_style_in_stable_prefix(intelligence: AgentIntelligence):
    prompt = intelligence._build_system_prompt(
        "assistant", None, [], {}, response_style_key="finance_analyst", persona_modifier="Volatile focus."
    )
    assert "## Response style: Finance Analyst" in prompt
    assert prompt.index("## Response style") < prompt.index("## Domain focus")


def test_build_system_prompt_agent_style_beats_requested(intelligence: AgentIntelligence):
    agent = {"id": "agent-1", "name": "Ava", "config": {"response_style": "support_specialist"}}
    prompt = intelligence._build_system_prompt(
        "agent_chat", agent, [], {}, response_style_key="finance_analyst"
    )
    assert "## Response style: Support Specialist" in prompt
    assert "## Response style: Finance Analyst" not in prompt


def test_build_system_prompt_spoken_style(intelligence: AgentIntelligence):
    prompt = intelligence._build_system_prompt(
        "assistant", None, [], {}, response_style_key="sales_advisor", spoken_mode=True
    )
    assert "## Response style: Sales Advisor" in prompt
    assert "Structure: Situation" not in prompt


# --- execute_task (jobs / workflows / ReAct) ------------------------------------


@pytest.mark.asyncio
async def test_execute_task_prompt_contains_agent_style(intelligence: AgentIntelligence):
    agent = {
        "id": "agent-1",
        "name": "Ops Agent",
        "role": "Operations",
        "config": {"response_style": "operations_analyst"},
    }
    with patch("app.operators.agent_intelligence.write_audit_event"), patch(
        "app.operators.agent_intelligence.load_agent_task_history", return_value=[]
    ):
        await intelligence.execute_task(org_id="org-1", agent=agent, task="Find the bottleneck", client=MagicMock())
    system_prompt = intelligence.react_engine.run.await_args.kwargs["system_prompt"]
    assert "## Response style: Operations Analyst" in system_prompt


@pytest.mark.asyncio
async def test_execute_task_uses_parameter_style_without_agent_style(intelligence: AgentIntelligence):
    agent = {"id": "agent-1", "name": "Agent", "config": {}}
    with patch("app.operators.agent_intelligence.write_audit_event"), patch(
        "app.operators.agent_intelligence.load_agent_task_history", return_value=[]
    ):
        await intelligence.execute_task(
            org_id="org-1",
            agent=agent,
            task="Summarize",
            parameters={"response_style": "deep_research_analyst"},
            client=MagicMock(),
        )
    system_prompt = intelligence.react_engine.run.await_args.kwargs["system_prompt"]
    assert "## Response style: Deep Research Analyst" in system_prompt


@pytest.mark.asyncio
async def test_execute_task_passes_knowledge_assignments_and_packs(intelligence: AgentIntelligence):
    agent = {
        "id": "agent-1",  # not a persisted UUID -> config-derived assignments
        "name": "Agent",
        "department": "sales",
        "config": {"knowledge_packs": ["pack.sales.core", {"id": "pack.sales.objections", "name": "Objections"}]},
    }
    fabric = MagicMock(
        return_value={"results": [{"citation": "Sales Core §1", "content": "Always confirm budget."}]}
    )
    with patch("app.operators.agent_intelligence.write_audit_event"), patch(
        "app.operators.agent_intelligence.load_agent_task_history", return_value=[]
    ), patch("app.knowledge_fabric.retrieval.retrieve_knowledge_fabric", fabric):
        await intelligence.execute_task(org_id="org-1", agent=agent, task="Qualify lead", client=MagicMock())
    params = intelligence.unified_retrieval.retrieve.await_args.kwargs["parameters"]
    source_ids = [row["sourceId"] for row in params["knowledge_assignments"]]
    assert source_ids == ["pack.sales.core", "pack.sales.objections"]
    assert fabric.call_args.kwargs["assigned_pack_ids"] == ["pack.sales.core", "pack.sales.objections"]
    system_prompt = intelligence.react_engine.run.await_args.kwargs["system_prompt"]
    assert "## Assigned Knowledge Packs" in system_prompt
    assert "Always confirm budget." in system_prompt


# --- streaming chat -----------------------------------------------------------


async def _run_streaming(intelligence: AgentIntelligence, **kwargs) -> str:
    from tests.conftest import patch_agent_streaming_dialogue_pipeline

    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    captured: dict[str, str] = {}

    async def fake_streaming(**run_kwargs):
        yield SimpleNamespace(kind="done", react_result=ReActResult(status=ReActStatus.COMPLETED, answer="ok"))

    real_build = intelligence._build_system_prompt

    def spy_build(*args, **build_kwargs):
        prompt = real_build(*args, **build_kwargs)
        captured["system_prompt"] = prompt
        return prompt

    intelligence._build_system_prompt = spy_build  # type: ignore[method-assign]
    intelligence.react_engine.run_streaming = fake_streaming
    intelligence.tool_registry.enrich_connected_integrations = AsyncMock(
        side_effect=lambda _client, _org_id, connected: connected
    )
    orchestrator = MagicMock()
    orchestrator.get_context_for_prompt = AsyncMock(return_value="")
    with patch("app.services.mcp_client_service.get_mcp_client_service") as mcp_svc:
        mcp_svc.return_value.get_enabled_tools_for_org = AsyncMock(return_value=[])
        with patch("app.operators.agent_intelligence.get_company_intelligence_orchestrator", return_value=orchestrator):
            with patch("app.operators.agent_intelligence.build_entity_context_section", AsyncMock(return_value="")):
                with patch("app.operators.agent_intelligence.get_org_context_service") as org_service:
                    org_service.return_value.get_context_bundle.return_value = ({"orgName": "Acme"}, "Org block")
                    with patch(
                        "app.operators.agent_intelligence.maybe_summarize_history",
                        AsyncMock(return_value=SimpleNamespace(messages=[], summary=None, summary_updated=False)),
                    ):
                        with patch_agent_streaming_dialogue_pipeline():
                            async for _event in intelligence.execute_task_streaming(
                                org_id="org-1",
                                user_id="user-1",
                                query=f"Say smoke-ok in one word ({uuid.uuid4().hex[:6]}).",
                                requested_tools=["agent_status"],
                                mode="standard",
                                client=client,
                                **kwargs,
                            ):
                                pass
    return captured.get("system_prompt", "")


@pytest.mark.asyncio
async def test_streaming_prompt_uses_requested_style(intelligence: AgentIntelligence):
    prompt = await _run_streaming(intelligence, explicit_persona="finance_analyst")
    assert "## Response style: Finance Analyst" in prompt


@pytest.mark.asyncio
async def test_streaming_agent_style_beats_user_requested_style(intelligence: AgentIntelligence):
    agent = {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Rex",
        "role": "Sales",
        "systems": [],
        "config": {"response_style": "sales_advisor"},
    }
    with patch("app.operators.agent_intelligence.resolve_agent_record", return_value=agent):
        prompt = await _run_streaming(
            intelligence, explicit_persona="finance_analyst", agent_id=agent["id"]
        )
    assert "## Response style: Sales Advisor" in prompt
    assert "## Response style: Finance Analyst" not in prompt


# --- unified LIVE / voice -------------------------------------------------------


def test_module_d_prompt_includes_style_and_agent_instructions():
    agent = {
        "id": "a1",
        "name": "Ava",
        "purpose": "Close renewals",
        "capabilities": ["renewal_forecasting", {"name": "pipeline_review"}],
        "guardrails": ["Never promise discounts"],
        "config": {"response_style": "executive_strategist", "system_prompt": "Prefer ARR figures."},
    }
    text = build_module_d_unified_system_prompt(agent=agent, response_style_key="friendly_assistant")
    assert "## Response style: Executive Strategist" in text
    assert "## Response style: Friendly Assistant" not in text
    assert "Primary purpose: Close renewals" in text
    assert "Assigned skills: renewal_forecasting, pipeline_review" in text
    assert "- Never promise discounts" in text
    assert "Prefer ARR figures." in text


def test_module_d_spoken_prompt_uses_spoken_style():
    text = build_module_d_unified_system_prompt(spoken_mode=True, response_style_key="support_specialist")
    assert "## Response style: Support Specialist" in text
    assert "Structure: One-line acknowledgement" not in text


@pytest.mark.asyncio
async def test_run_unified_turn_shadow_system_prompt_has_style():
    from app.services.unified_turn_reasoning_service import run_unified_turn_shadow
    from tests.services.test_unified_turn_reasoning import _mock_narrowed, _mock_stream_client

    mock_client = _mock_stream_client(content="Sure.")
    mock_router = MagicMock()
    mock_router._openai = mock_client
    settings = MagicMock(
        unified_turn_shadow_enabled=True,
        unified_turn_shadow_max_tools=24,
        unified_turn_embedding_tool_retrieval=False,
        unified_turn_task_max_tools=16,
        unified_turn_task_model_tier="",
        openai_api_key="sk-test",
    )
    with patch("app.services.unified_turn_reasoning_service.get_tool_registry") as reg_patch, patch(
        "app.services.unified_turn_reasoning_service.get_model_router", return_value=mock_router
    ), patch(
        "app.services.unified_turn_reasoning_service.narrow_tools_for_turn", return_value=_mock_narrowed([])
    ):
        reg_patch.return_value.get_tools_for_agent.return_value = []
        await run_unified_turn_shadow(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message="thanks!",
            task_state={},
            conversation_history=[],
            connected_integrations=[],
            settings=settings,
            response_style_key="marketing_operator",
        )
    system = mock_client.chat.completions.create.await_args.kwargs["messages"][0]["content"]
    assert "## Response style: Marketing Operator" in system

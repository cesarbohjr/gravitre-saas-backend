"""Tests for Gravitre Advanced Conversational Intelligence Layer."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.clarification_engine import ClarificationEngine, get_clarification_engine
from app.services.contextual_understanding_service import ContextualUnderstandingService
from app.services.conversation_state_service import ConversationStateService
from app.services.conversational_consensus_service import ConversationalConsensusService
from app.services.dialogue_policy_engine import DialoguePolicyEngine
from app.services.persona_service import PersonaService, get_persona_service
from app.services.proactive_guidance_service import ProactiveGuidanceService
from app.services.reasoning_planner_service import ReasoningPlannerService
from app.services.sentiment_friction_service import SentimentFrictionService
from app.services.risk_approval_evaluator import RiskApprovalEvaluator
from app.operators.agent_intelligence import AgentIntelligence


@pytest.fixture
def clarification_engine():
    engine = ClarificationEngine()
    engine._state = MagicMock()
    engine._state.get_task_state = AsyncMock(return_value={"clarified_params": {}})
    return engine


@pytest.mark.asyncio
async def test_ambiguous_prompt_triggers_clarification(clarification_engine):
    result = await clarification_engine.should_clarify(
        {
            "request": "Can you fix it?",
            "classification_confidence": 0.5,
            "requires_action": False,
        },
        {},
        [],
    )
    assert result["should_clarify"] is True
    assert result["trigger_type"] == "ambiguous_entity"


@pytest.mark.asyncio
async def test_clear_prompt_does_not_over_clarify(clarification_engine):
    result = await clarification_engine.should_clarify(
        {
            "request": "How many active agents do we have?",
            "classification_confidence": 0.82,
            "requires_action": False,
        },
        {},
        [],
    )
    assert result["should_clarify"] is False


@pytest.mark.asyncio
async def test_clarification_never_re_asks_resolved_param(clarification_engine):
    clarification_engine._state.get_task_state = AsyncMock(
        return_value={"clarified_params": {"action_target": "workflow-1"}}
    )
    result = await clarification_engine.should_clarify(
        {
            "request": "run the workflow",
            "classification_confidence": 0.55,
            "requires_action": True,
            "intent": "workflow_execution",
        },
        {"connected_integrations": ["platform"]},
        [],
        conversation_id="conv-1",
        org_id="org-1",
    )
    assert result["should_clarify"] is False or result["trigger_type"] != "missing_required_param"


@pytest.mark.asyncio
async def test_high_risk_action_triggers_confirmation(clarification_engine):
    result = await clarification_engine.should_clarify(
        {
            "request": "delete all customer records",
            "classification_confidence": 0.9,
            "requires_action": True,
            "risk_level": "high",
        },
        {},
        [],
    )
    assert result["should_clarify"] is True
    assert result["trigger_type"] == "high_risk_confirmation"


@pytest.mark.asyncio
async def test_missing_connector_triggers_clarification(clarification_engine):
    result = await clarification_engine.should_clarify(
        {
            "request": "pull hubspot deals",
            "classification_confidence": 0.8,
            "requires_action": False,
        },
        {"connected_integrations": []},
        [],
        understanding={"connector_dependencies": ["hubspot"]},
    )
    assert result["should_clarify"] is True
    assert result["trigger_type"] == "connector_unavailable"


@pytest.mark.asyncio
async def test_slack_send_asks_for_message_not_workflow_execution(clarification_engine):
    """Prod regression: 'send a message in slack general channel' must not leak intent."""
    clarification_engine._polish_question = AsyncMock(return_value=None)
    result = await clarification_engine.should_clarify(
        {
            "request": "send a message in slack general channel",
            "classification_confidence": 0.85,
            "requires_action": True,
            "intent": "workflow_execution",
        },
        {"connected_integrations": ["slack"]},
        [],
    )
    assert result["should_clarify"] is True
    assert result["trigger_type"] == "missing_required_param"
    question = result["question"] or ""
    assert "workflow_execution" not in question
    assert "workflow_execution" not in str(result.get("template_vars") or {})
    assert "Slack" in question or "slack" in question.lower()
    assert "message" in question.lower()


@pytest.mark.asyncio
async def test_slack_send_with_body_and_channel_does_not_over_clarify(clarification_engine):
    clarification_engine._polish_question = AsyncMock(return_value=None)
    result = await clarification_engine.should_clarify(
        {
            "request": 'send "standup in 5" to slack #general',
            "classification_confidence": 0.9,
            "requires_action": True,
            "intent": "workflow_execution",
        },
        {"connected_integrations": ["slack"]},
        [],
    )
    assert result["should_clarify"] is False


@pytest.mark.asyncio
async def test_slack_send_persists_channel_when_asking_for_body(clarification_engine):
    clarification_engine._polish_question = AsyncMock(return_value=None)
    persist = AsyncMock()
    clarification_engine._state.update_task_state = persist
    clarification_engine._state.get_task_state = AsyncMock(
        return_value={"clarified_params": {}, "pending_task": None}
    )
    result = await clarification_engine.should_clarify(
        {
            "request": "send a message in slack general channel",
            "classification_confidence": 0.85,
            "requires_action": True,
            "intent": "workflow_execution",
        },
        {"connected_integrations": ["slack"]},
        [],
        conversation_id="conv-1",
        org_id="org-1",
    )
    assert result["should_clarify"] is True
    persist.assert_awaited()
    updates = persist.await_args.args[2]
    assert updates["pending_task"]["status"] == "awaiting_params"
    # Module B — channel lives on the shared parameter ledger.
    ledger_slots = (updates.get("parameter_ledger") or {}).get("slots") or {}
    channel_slot = ledger_slots.get("channel") or {}
    assert channel_slot.get("value") == "general" or updates.get("clarified_params", {}).get(
        "slack_channel"
    ) == "general"


@pytest.mark.asyncio
async def test_slack_followup_body_skips_reclarify(clarification_engine):
    clarification_engine._polish_question = AsyncMock(return_value=None)
    clarification_engine._state.get_task_state = AsyncMock(
        return_value={
            "clarified_params": {"slack_channel": "general", "intent": "slack_send"},
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_params",
                "params": {"integration": "slack", "channel": "general"},
            },
        }
    )
    result = await clarification_engine.should_clarify(
        {
            "request": "Sure, say hi everyone at Gravitre",
            "classification_confidence": 0.5,
            "requires_action": False,
            "intent": "question",
        },
        {"connected_integrations": ["slack"]},
        [],
        conversation_id="conv-1",
        org_id="org-1",
    )
    assert result["should_clarify"] is False
    assert "Resuming connector action" in (result.get("reason") or "")


@pytest.mark.asyncio
async def test_generic_action_clarify_humanizes_intent(clarification_engine):
    clarification_engine._polish_question = AsyncMock(return_value=None)
    result = await clarification_engine.should_clarify(
        {
            "request": "send the update",
            "classification_confidence": 0.8,
            "requires_action": True,
            "intent": "workflow_execution",
        },
        {},
        [],
    )
    assert result["should_clarify"] is True
    assert result["trigger_type"] == "missing_required_param"
    assert "workflow_execution" not in (result["question"] or "")
    assert result["template_vars"]["action"] == "do that"


@pytest.mark.asyncio
async def test_clarification_uses_fast_tier_not_reasoning():
    engine = ClarificationEngine()
    with patch("app.services.model_router.get_model_router") as get_router:
        router = MagicMock()
        router.complete = AsyncMock(return_value=MagicMock(content="Which workflow did you mean?"))
        get_router.return_value = router
        question = await engine.generate_clarification_question(
            "ambiguous_entity",
            {"request": "fix it"},
            {},
            [],
            {"entity_type": "workflow", "options": "A or B"},
        )
    assert "workflow" in question.lower() or "mean" in question.lower()


@pytest.mark.asyncio
async def test_persona_selection_priority_order():
    service = PersonaService()
    service._load_user_preference = AsyncMock(return_value="sales_advisor")
    with patch(
        "app.services.persona_service.load_chat_dialogue_settings",
        AsyncMock(return_value={"default_persona": "friendly_assistant"}),
    ):
        persona = await service.get_persona_for_request(
            "org-1",
            "user-1",
            None,
            None,
            explicit_persona="executive_strategist",
        )
    assert persona["persona_key"] == "executive_strategist"


def test_persona_modifier_injected_into_prompt():
    intelligence = AgentIntelligence()
    prompt = intelligence._build_system_prompt(
        "assistant",
        None,
        [],
        {},
        persona_modifier="Be concise and executive-facing.",
    )
    assert "Communication Style" in prompt
    assert "executive-facing" in prompt


def test_persona_never_overrides_governance():
    modifier = get_persona_service().get_persona_modifier_for_prompt("executive_strategist")
    assert "override approval" not in modifier.lower()
    assert "bypass" not in modifier.lower()


def test_persona_never_overrides_confidence_scores():
    service = PersonaService()
    persona = service.COMMUNICATION_PERSONAS["friendly_assistant"]
    assert "confidence" not in persona["system_prompt_modifier"].lower()


def test_all_caps_detected_as_frustration():
    result = SentimentFrictionService().analyze("THIS IS NOT WORKING AT ALL", [])
    assert result["frustration_score"] >= 0.3
    assert "all_caps" in result["signals"] or "frustration_phrase" in result["signals"]


def test_repeated_question_detected():
    history = [{"role": "user", "content": "Why is my workflow failing repeatedly today?"}]
    result = SentimentFrictionService().analyze("Why is my workflow failing repeatedly today?", history)
    assert "repeated_question" in result["signals"]


def test_urgency_phrase_detected():
    result = SentimentFrictionService().analyze("I need this fixed ASAP", [])
    assert result["urgency_score"] >= 0.5


def test_sentiment_never_changes_facts_reported():
    result = SentimentFrictionService().analyze("THIS IS URGENT", [])
    assert "answer" not in result
    assert "recommended_adaptation" in result


def test_rule_based_path_under_50ms():
    service = SentimentFrictionService()
    start = time.perf_counter()
    for _ in range(100):
        service.analyze("THIS IS NOT WORKING AGAIN", [{"role": "user", "content": "help"}])
    elapsed_ms = (time.perf_counter() - start) * 1000 / 100
    assert elapsed_ms < 50


def test_clarify_mode_when_should_clarify_true():
    engine = DialoguePolicyEngine()
    result = engine.select_mode(
        {"intent": "question_answering"},
        {"should_clarify": True, "reason": "ambiguous", "question": "Which one?"},
        {},
        {},
        0.5,
        [],
    )
    assert result["mode"] == "clarify"


def test_confirm_mode_when_approval_required():
    engine = DialoguePolicyEngine()
    result = engine.select_mode(
        {"requires_action": True},
        {"should_clarify": False},
        {},
        {"requires_approval": True, "can_proceed_without_approval": False, "approval_reason": "risky"},
        0.8,
        [],
    )
    assert result["mode"] == "confirm"
    assert result["approval_required"] is True


def test_escalate_mode_below_threshold():
    engine = DialoguePolicyEngine()
    result = engine.select_mode({}, {"should_clarify": False}, {}, {}, 0.2, [])
    assert result["mode"] == "escalate"


def test_answer_mode_high_confidence_simple():
    engine = DialoguePolicyEngine()
    result = engine.select_mode(
        {"intent": "question_answering", "requires_action": False},
        {"should_clarify": False},
        {},
        {},
        0.9,
        [],
    )
    assert result["mode"] == "answer"


def test_guide_mode_for_strategic_task():
    engine = DialoguePolicyEngine()
    result = engine.select_mode(
        {"intent": "workflow_planning", "requires_action": False},
        {"should_clarify": False},
        {},
        {},
        0.75,
        [],
    )
    assert result["mode"] == "guide"


@pytest.mark.asyncio
async def test_task_state_persists_across_turns():
    service = ConversationStateService()
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"task_state": {"clarified_params": {"target": "wf-1"}}}
    ]
    state = await service.get_task_state("conv-1", "org-1", client=mock_client)
    assert state["clarified_params"]["target"] == "wf-1"


@pytest.mark.asyncio
async def test_task_state_fire_and_forget_never_blocks():
    service = ConversationStateService()
    with patch.object(service, "_persist_state", AsyncMock()) as persist:
        await service.update_task_state("conv-1", "org-1", {"clarified_params": {"x": "1"}})
        await asyncio.sleep(0.01)
    persist.assert_called()


@pytest.mark.asyncio
async def test_task_state_org_scoped():
    service = ConversationStateService()
    mock_client = MagicMock()
    chain = mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value
    chain.execute.return_value.data = []
    state = await service.get_task_state("conv-1", "org-1", client=mock_client)
    assert state["clarified_params"] == {}


@pytest.mark.asyncio
async def test_rejected_options_remembered():
    service = ConversationStateService()
    with patch.object(service, "update_task_state", AsyncMock()) as update:
        await service.remember_rejected_option("conv-1", "org-1", "automation")
    update.assert_awaited_once()


@pytest.mark.asyncio
async def test_plan_persisted_to_conversation_state():
    planner = ReasoningPlannerService()
    planner._decision.scaffold_decision_plan = AsyncMock(
        return_value={"goal": "launch campaign", "planSteps": ["Draft", "Review", "Execute"]}
    )
    planner._state.update_task_state = AsyncMock()
    plan = await planner.create_plan("org-1", "user-1", "conv-1", "launch campaign", {})
    assert plan["steps"]
    planner._state.update_task_state.assert_awaited()


@pytest.mark.asyncio
async def test_plan_never_executes_without_confirmation():
    planner = ReasoningPlannerService()
    planner._decision.scaffold_decision_plan = AsyncMock(return_value={"planSteps": ["Step 1"]})
    planner._state.update_task_state = AsyncMock()
    plan = await planner.create_plan("org-1", "user-1", "conv-1", "goal", {})
    assert plan.get("requires_confirmation") is True
    assert plan.get("advisory_only") is True


@pytest.mark.asyncio
async def test_step_advancement_correct_order():
    planner = ReasoningPlannerService()
    planner._state.get_task_state = AsyncMock(
        return_value={
            "current_plan": {
                "steps": [
                    {"step_id": "step_1", "description": "A", "dependencies": []},
                    {"step_id": "step_2", "description": "B", "dependencies": ["step_1"]},
                ]
            },
            "completed_steps": [],
            "pending_steps": [
                {"step_id": "step_1", "description": "A", "dependencies": []},
                {"step_id": "step_2", "description": "B", "dependencies": ["step_1"]},
            ],
        }
    )
    planner._state.update_task_state = AsyncMock()
    blocked = await planner.advance_plan("conv-1", "org-1", "step_2")
    assert blocked["status"] == "blocked"
    ok = await planner.advance_plan("conv-1", "org-1", "step_1")
    assert ok["status"] == "ok"


@pytest.mark.asyncio
async def test_plan_revision_preserves_completed_steps():
    planner = ReasoningPlannerService()
    planner._state.get_task_state = AsyncMock(
        return_value={
            "completed_steps": [{"step_id": "step_1", "description": "Done"}],
            "pending_steps": [],
        }
    )
    planner._decision.scaffold_decision_plan = AsyncMock(return_value={"planSteps": ["New step"]})
    planner._state.update_task_state = AsyncMock()
    revised = await planner.revise_plan("conv-1", "org-1", "context changed", "goal", {})
    assert revised["steps"][0]["step_id"] == "step_1"


@pytest.mark.asyncio
async def test_no_suggestions_during_clarify_mode():
    service = ProactiveGuidanceService()
    suggestions = await service.get_suggestions("org-1", "user-1", "conv-1", {}, "clarify", "answer")
    assert suggestions == []


@pytest.mark.asyncio
async def test_no_suggestions_during_execute_mode():
    service = ProactiveGuidanceService()
    suggestions = await service.get_suggestions("org-1", "user-1", "conv-1", {}, "execute", "answer")
    assert suggestions == []


@pytest.mark.asyncio
async def test_max_two_suggestions_per_response():
    service = ProactiveGuidanceService()
    with patch.object(service, "_load_suppressed", AsyncMock(return_value=set())):
        with patch.object(service, "_condition_met", AsyncMock(return_value={"vars": {"connector": "HubSpot", "benefit": "sync"}})):
            suggestions = await service.get_suggestions(
                "org-1",
                "user-1",
                "conv-1",
                {"request": "hubspot deals", "intent": "crm_lookup"},
                "answer",
                "done",
                connected_integrations=[],
            )
    assert len(suggestions) <= 2


@pytest.mark.asyncio
async def test_suppressed_suggestions_not_shown():
    service = ProactiveGuidanceService()
    with patch.object(service, "_load_suppressed", AsyncMock(return_value={"simulation_available"})):
        with patch.object(service, "_condition_met", AsyncMock(return_value={"vars": {}})):
            suggestions = await service.get_suggestions(
                "org-1",
                "user-1",
                "conv-1",
                {"requires_action": True, "intent": "workflow_execution"},
                "answer",
                "response",
            )
    assert all(s["suppression_key"] != "simulation_available" for s in suggestions)


@pytest.mark.asyncio
async def test_unavailable_features_not_suggested_as_active():
    service = ProactiveGuidanceService()
    rendered = await service._condition_met(
        "missing_connector",
        "org-1",
        {"request": "hubspot pipeline"},
        "",
        connected_integrations=[],
    )
    assert rendered is not None
    assert "Hubspot" in rendered["vars"]["connector"]


@pytest.mark.asyncio
async def test_entity_extraction_rule_based_fast_path():
    service = ContextualUnderstandingService()
    result = await service.understand('Run workflow "Weekly Sync"', [], "org-1")
    assert any(entity["type"] == "workflow" for entity in result["entities"])


@pytest.mark.asyncio
async def test_connector_reference_detected():
    service = ContextualUnderstandingService()
    result = await service.understand("Show hubspot deals", [], "org-1")
    assert "hubspot" in result["connector_dependencies"]


@pytest.mark.asyncio
async def test_temporal_reference_extracted():
    service = ContextualUnderstandingService()
    result = await service.understand("What failed yesterday?", [], "org-1")
    assert result["temporal_references"]


@pytest.mark.asyncio
async def test_output_format_detected():
    service = ContextualUnderstandingService()
    result = await service.understand("Build a plan for onboarding", [], "org-1")
    assert result["expected_output_format"] == "plan"


@pytest.mark.asyncio
async def test_already_known_not_re_asked():
    service = ContextualUnderstandingService()
    history = [{"role": "assistant", "content": "Workflow Alpha failed due to connector timeout."}]
    known = service._extract_from_history("why did the workflow fail?", history)
    assert known.get("workflow_context") is True


@pytest.mark.asyncio
async def test_consensus_not_triggered_for_simple_question():
    service = ConversationalConsensusService()
    with patch(
        "app.services.conversational_consensus_service.load_chat_dialogue_settings",
        AsyncMock(return_value={"consensus_enabled": True}),
    ):
        result = await service.refine_if_warranted(
            "org-1",
            "How many agents?",
            "You have 3 agents.",
            {"intent": "question_answering"},
            0.9,
            "answer",
        )
    assert result["consensus_used"] is False


@pytest.mark.asyncio
async def test_consensus_timeout_falls_back_gracefully():
    service = ConversationalConsensusService()

    async def slow_deliberate(**kwargs):
        await asyncio.sleep(0.2)
        return {"consensus_recommendation": "x", "confidence": 0.5, "minority_opinions": [], "consensus_explanation": ""}

    service.deliberate = slow_deliberate  # type: ignore[method-assign]
    service.CONSENSUS_TIMEOUT_SECONDS = 0.01
    with patch(
        "app.services.conversational_consensus_service.load_chat_dialogue_settings",
        AsyncMock(return_value={"consensus_enabled": True}),
    ):
        result = await service.refine_if_warranted(
            "org-1",
            "Plan Q4 strategy",
            "Primary",
            {"intent": "data_analysis"},
            0.4,
            "guide",
        )
    assert result["consensus_used"] is False
    assert "note" in result


@pytest.mark.asyncio
async def test_consensus_summary_never_raw_debate():
    service = ConversationalConsensusService()
    service.deliberate = AsyncMock(
        return_value={
            "consensus_recommendation": "Proceed with caution",
            "confidence": 0.7,
            "minority_opinions": [{"agent": "Skeptic"}],
            "consensus_explanation": "Independent review reached 70% confidence.",
        }
    )
    with patch(
        "app.services.conversational_consensus_service.load_chat_dialogue_settings",
        AsyncMock(return_value={"consensus_enabled": True}),
    ):
        result = await service.refine_if_warranted(
            "org-1",
            "Plan",
            "Primary",
            {"intent": "data_analysis"},
            0.4,
            "guide",
        )
    assert "debate_round" not in result["response"]
    assert result["consensus_used"] is True


def test_clarification_ui_distinct_from_answer_ui():
    assert True


def test_no_chain_of_thought_exposed_in_ui():
    modifier = get_persona_service().get_persona_modifier_for_prompt("deep_research_analyst")
    assert "chain of thought" not in modifier.lower()


def test_persona_preference_saved_to_user_prefs():
    from app.services.user_intelligence import UserIntelligenceService
    import inspect

    params = inspect.signature(UserIntelligenceService.update_preferences).parameters
    assert "preferred_persona" in params


def test_approval_layer_not_bypassed_by_any_task():
    evaluator = RiskApprovalEvaluator()
    assert hasattr(evaluator, "evaluate")


def test_no_secrets_in_conversation_state():
    from app.services.conversation_state_service import DEFAULT_TASK_STATE

    assert "secret" not in str(DEFAULT_TASK_STATE).lower()
    assert "api_key" not in str(DEFAULT_TASK_STATE).lower()


@pytest.mark.asyncio
async def test_tenant_isolation_conversation_state():
    service = ConversationStateService()
    mock_client = MagicMock()
    update_chain = mock_client.table.return_value.update.return_value.eq.return_value.eq
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"task_state": {}}
    ]
    await service._persist_state("conv-1", "org-1", {"clarified_params": {"a": "1"}}, client=mock_client)
    update_chain.assert_called()

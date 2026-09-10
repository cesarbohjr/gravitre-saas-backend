"""Standing CI: canned shortcuts and spoken lite-path cannot diverge task execution.

Typed chat (assistant.py) and spoken (Pipecat / spoken_mode=True) must reach the
same kernel/LIVE gates for real operator jobs. Conversational chitchat may still
use spoken latency shortcuts.
"""

from __future__ import annotations

import pytest

from app.routers import assistant as assistant_module
from app.services.conversational_turn_gate import (
    ambiguous_open_clarify_reply,
    definition_brief_reply,
    heuristic_turn_shape,
    is_human_moment_venting_no_ask,
)
from app.services.frontend_ia_nav_faq import match_frontend_ia_nav_faq
from app.services.operator_task_intent import (
    should_keep_full_reasoning_for_spoken,
    should_skip_unified_live_guards,
    use_spoken_lite_path,
)
from tests.services.task_execution_parity_fixtures import (
    AMBIGUOUS_CLARIFY,
    CONNECTOR_LOOKUP,
    GOOGLE_ADS_CAMPAIGN_BRIEF,
    MULTI_PARAM_WRITE,
    SEO_PLUS_GOOGLE_ADS,
    VENTING_PLUS_GOOGLE_ADS,
)


def _assert_reaches_reasoning(message: str) -> None:
    assert match_frontend_ia_nav_faq(message) is None
    assert ambiguous_open_clarify_reply(message) is None
    assert definition_brief_reply(message) is None
    assert is_human_moment_venting_no_ask(message) is False
    assert not assistant_module._response_cache_eligible(message)
    assert should_keep_full_reasoning_for_spoken(message)
    assert not use_spoken_lite_path(
        spoken_mode=True,
        routing_tier="simple",
        message=message,
    )
    assert not should_skip_unified_live_guards(
        spoken_mode=True,
        reasoning_depth="conversational",
        has_pending=False,
        message=message,
    )
    assert not should_skip_unified_live_guards(
        spoken_mode=False,
        reasoning_depth="full",
        has_pending=False,
        message=message,
    )


def test_google_ads_brief_reaches_reasoning_typed_and_spoken() -> None:
    _assert_reaches_reasoning(GOOGLE_ADS_CAMPAIGN_BRIEF)


def test_connector_lookup_reaches_reasoning_typed_and_spoken() -> None:
    _assert_reaches_reasoning(CONNECTOR_LOOKUP)


def test_multi_param_write_reaches_reasoning_typed_and_spoken() -> None:
    _assert_reaches_reasoning(MULTI_PARAM_WRITE)


def test_seo_prefix_plus_google_ads_is_not_canned_clarify() -> None:
    """Mutation of the FAQ-class bug: prefix keyword + real job must fall through."""
    assert ambiguous_open_clarify_reply(AMBIGUOUS_CLARIFY) is not None
    assert ambiguous_open_clarify_reply(SEO_PLUS_GOOGLE_ADS) is None
    _assert_reaches_reasoning(SEO_PLUS_GOOGLE_ADS)


def test_venting_plus_google_ads_is_not_human_moment_canned() -> None:
    assert is_human_moment_venting_no_ask("ugh this is so frustrating today") is True
    assert is_human_moment_venting_no_ask(VENTING_PLUS_GOOGLE_ADS) is False
    decision = heuristic_turn_shape(VENTING_PLUS_GOOGLE_ADS)
    assert decision is None or decision.shape != "conversational" or decision.reason != "human_moment_venting_no_ask"
    _assert_reaches_reasoning(VENTING_PLUS_GOOGLE_ADS)


def test_narrow_ambiguous_open_still_clarifies() -> None:
    reply = ambiguous_open_clarify_reply(AMBIGUOUS_CLARIFY)
    assert reply is not None
    assert "?" in reply


def test_operator_task_forces_classical_defer_on_conversational_live_reply() -> None:
    from app.services.chat_orchestration_service import ChatOrchestrationService
    from app.services.operator_task_intent import should_force_live_connector_pipeline
    from app.services.unified_turn_classical_fallback import should_defer_unified_turn_live_to_classical

    assert should_force_live_connector_pipeline(GOOGLE_ADS_CAMPAIGN_BRIEF)
    assert ChatOrchestrationService.is_orchestration_intent(
        GOOGLE_ADS_CAMPAIGN_BRIEF, {}, []
    )
    assert should_defer_unified_turn_live_to_classical(
        mode_key="fast",
        outcome_kind="conversational_reply",
        message=GOOGLE_ADS_CAMPAIGN_BRIEF,
        needs_tool_sse=True,
    )
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="fast",
        outcome_kind="conversational_reply",
        message=GOOGLE_ADS_CAMPAIGN_BRIEF,
        needs_tool_sse=False,
    )


def test_spoken_and_typed_share_full_depth_for_operator_tasks() -> None:
    for message in (GOOGLE_ADS_CAMPAIGN_BRIEF, CONNECTOR_LOOKUP, MULTI_PARAM_WRITE):
        typed_skip = should_skip_unified_live_guards(
            spoken_mode=False,
            reasoning_depth="full",
            has_pending=False,
            message=message,
        )
        spoken_skip = should_skip_unified_live_guards(
            spoken_mode=True,
            reasoning_depth="full",
            has_pending=False,
            message=message,
        )
        assert typed_skip is False
        assert spoken_skip is False
        assert should_keep_full_reasoning_for_spoken(message)


@pytest.mark.asyncio
async def test_operator_task_skips_live_model_and_runs_orchestration() -> None:
    """Spoken Register 5 must not generate before ChatOrchestration for Google Ads."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.unified_turn_reasoning_service import apply_unified_turn_live

    orch_message = (
        "I planned a **5-step orchestration**, but **nothing is runnable** — "
        "every step is blocked:\n\n1. Google Ads (not connected)"
    )
    shadow = AsyncMock(side_effect=AssertionError("LIVE model must not run for operator tasks"))
    orch_svc = MagicMock()
    orch_svc.process_turn = AsyncMock(
        return_value={
            "stop_pipeline": True,
            "message": orch_message,
            "dialogue_mode": "confirm",
            "task_state": {"pending_task": None},
            "pending_task": None,
            "workflow_status": "blocked",
            "answer_explanation": "Multi-step connector orchestration",
        }
    )
    settings = MagicMock()
    settings.unified_turn_live_enabled = True

    with (
        patch(
            "app.services.unified_turn_pending_live.resolve_unified_live_channel_override_reply",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.unified_turn_pending_live.resolve_unified_live_meta_capability_reply",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.unified_turn_pending_live.resolve_unified_live_pending_reply",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.pending_reply_classifier.has_pending_family",
            return_value=False,
        ),
        patch(
            "app.services.retrieve_plan_gate.retrieve_plan_or_none",
            return_value=None,
        ),
        patch(
            "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
            new=shadow,
        ),
        patch(
            "app.services.unified_turn_reasoning_service.emit_unified_turn_shadow_audit",
        ),
        patch(
            "app.services.chat_orchestration_service.get_chat_orchestration_service",
            return_value=orch_svc,
        ),
    ):
        out = await apply_unified_turn_live(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-ads-skip-live",
            message=GOOGLE_ADS_CAMPAIGN_BRIEF,
            task_state={},
            conversation_history=[],
            connected_integrations=["google_ads", "hubspot"],
            client=MagicMock(),
            settings=settings,
            spoken_mode=True,
        )

    shadow.assert_not_called()
    orch_svc.process_turn.assert_awaited_once()
    assert out is not None
    assert out.get("stop_pipeline") is True
    assert "5-step orchestration" in (out.get("message") or "")
    assert "enough information yet to do that safely" not in (out.get("message") or "").lower()
    assert "skipped spoken LIVE" in str(out.get("answer_explanation") or "")


@pytest.mark.asyncio
async def test_operator_task_orch_beats_live_create_workflow_proposal() -> None:
    """Connected Ads briefs must not become a 'Problem Aware' draft-workflow card."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.unified_turn_reasoning_service import (
        UnifiedTurnShadowResult,
        apply_unified_turn_live,
    )

    shadow = UnifiedTurnShadowResult(
        outcome_kind="connector_tool_proposal",
        user_message=(
            "I'll create a draft workflow for **Problem Aware**.\n\n"
            "Reply **yes** to create it now, or tell me what to adjust."
        ),
        tool_name="assistant_create_workflow",
        tool_invoke_action="assistant.create_workflow",
        connected_integrations=["google_ads"],
        model="test",
        needs_tool_sse=False,
    )
    orch_message = (
        "I planned a **4-step orchestration**. Reply **yes** to approve "
        "Google Ads campaign creation."
    )
    orch_svc = MagicMock()
    orch_svc.process_turn = AsyncMock(
        return_value={
            "stop_pipeline": True,
            "message": orch_message,
            "dialogue_mode": "confirm",
            "task_state": {},
            "pending_task": {"type": "connector_orchestration", "status": "awaiting_plan_confirm"},
            "workflow_status": "awaiting_plan_confirm",
        }
    )
    settings = MagicMock()
    settings.unified_turn_live_enabled = True

    with (
        patch(
            "app.services.unified_turn_pending_live.resolve_unified_live_channel_override_reply",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.unified_turn_pending_live.resolve_unified_live_meta_capability_reply",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.unified_turn_pending_live.resolve_unified_live_pending_reply",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.pending_reply_classifier.has_pending_family",
            return_value=False,
        ),
        patch(
            "app.services.retrieve_plan_gate.retrieve_plan_or_none",
            return_value=None,
        ),
        patch(
            "app.services.unified_turn_reasoning_service._pack_common_intents_match",
            return_value=True,
        ),
        patch(
            "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
            new=AsyncMock(return_value=shadow),
        ),
        patch(
            "app.services.unified_turn_reasoning_service.emit_unified_turn_shadow_audit",
        ),
        patch(
            "app.services.chat_orchestration_service.get_chat_orchestration_service",
            return_value=orch_svc,
        ),
    ):
        out = await apply_unified_turn_live(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-ads-workflow-steal",
            message=GOOGLE_ADS_CAMPAIGN_BRIEF,
            task_state={},
            conversation_history=[],
            connected_integrations=["google_ads"],
            client=MagicMock(),
            settings=settings,
            spoken_mode=True,
        )

    orch_svc.process_turn.assert_awaited_once()
    assert out is not None
    msg = out.get("message") or ""
    assert "4-step orchestration" in msg
    assert "draft workflow" not in msg.lower()
    assert "Problem Aware" not in msg

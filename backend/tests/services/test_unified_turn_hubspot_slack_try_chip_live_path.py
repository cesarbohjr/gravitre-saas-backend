"""Exact HubSpot+Slack AI Chat TRY chip through LIVE path (same pattern as MSP)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.chat_orchestration_service import OrchestrationStep
from app.services.unified_turn_classical_fallback import (
    message_requires_classical_tool_sse,
    should_defer_unified_turn_live_to_classical,
)

HS_SLACK_TRY = (
    "Search HubSpot for high-intent leads and draft a follow-up in Slack for approval"
)


def test_hubspot_slack_try_chip_no_longer_bare_slack_keyword_defer():
    """F2: bare \\bslack\\b removed — defer via LIVE needs_tool_sse / orch intent."""
    assert message_requires_classical_tool_sse(HS_SLACK_TRY) is False
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="fast",
        outcome_kind="conversational_reply",
        message=HS_SLACK_TRY,
        needs_tool_sse=False,
    )
    assert should_defer_unified_turn_live_to_classical(
        mode_key="fast",
        outcome_kind="conversational_reply",
        message=HS_SLACK_TRY,
        needs_tool_sse=True,
    )


@pytest.mark.asyncio
async def test_apply_unified_turn_live_hubspot_slack_try_chip_stages_orch_before_defer():
    """LIVE must stage HubSpot→Slack plan confirm before bare classical defer.

    Same failure class as MSP: conversational_reply + SSE defer → classical luck.
    Structural fix: orchestration intents stage on LIVE before defer.
    """
    from app.services.unified_turn_reasoning_service import (
        UnifiedTurnShadowResult,
        apply_unified_turn_live,
    )

    shadow = UnifiedTurnShadowResult(
        outcome_kind="conversational_reply",
        user_message="I can help with that.",
        connected_integrations=["hubspot", "slack"],
        model="test",
    )
    steps = [
        OrchestrationStep(
            step_id="step_1",
            segment="Search HubSpot for high-intent leads",
            label="Search contacts",
            kind="read",
            supported=True,
            requires_approval=False,
            plan=ConnectorActionPlan(
                tool_name="hubspot_contacts_search",
                invoke_action="hubspot.contacts.search",
                integration="hubspot",
                kind="read",
                label="Search contacts",
                args={"query": "high-intent"},
            ),
        ),
        OrchestrationStep(
            step_id="step_2",
            segment="draft a follow-up in Slack for approval",
            label="Post message",
            kind="write",
            supported=True,
            requires_approval=True,
            plan=ConnectorActionPlan(
                tool_name="slack_post_message",
                invoke_action="slack.post_message",
                integration="slack",
                kind="write",
                label="Post message",
                args={"text": "follow-up"},
                destructive=True,
                requires_approval=True,
            ),
        ),
    ]
    refreshed = {
        "pending_task": {
            "type": "connector_orchestration",
            "status": "awaiting_plan_confirm",
            "params": {
                "goal": HS_SLACK_TRY,
                "steps": [s.to_dict() for s in steps],
            },
        }
    }
    state = MagicMock()
    state.update_task_state = AsyncMock()
    state.get_task_state = AsyncMock(
        side_effect=[
            {"pending_task": None, "clarified_params": {}},
            refreshed,
            refreshed,
        ]
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
            "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
            new=AsyncMock(return_value=shadow),
        ),
        patch(
            "app.services.unified_turn_reasoning_service.emit_unified_turn_shadow_audit",
        ),
        patch(
            "app.services.conversation_state_service.get_conversation_state_service",
            return_value=state,
        ),
        patch(
            "app.services.chat_orchestration_service.get_conversation_state_service",
            return_value=state,
        ),
        patch(
            "app.services.chat_orchestration_service.ChatOrchestrationService._build_plan",
            new=AsyncMock(return_value=steps),
        ),
    ):
        out = await apply_unified_turn_live(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-try-hs-slack",
            message=HS_SLACK_TRY,
            task_state={},
            conversation_history=[],
            connected_integrations=["hubspot", "slack"],
            client=MagicMock(),
            settings=settings,
        )

    assert out is not None, (
        "LIVE deferred HubSpot+Slack TRY chip to classical (same landmine class as MSP)"
    )
    assert out.get("stop_pipeline") is True
    assert out.get("dialogue_mode") == "confirm"
    msg = (out.get("message") or "").lower()
    assert "orchestration" in msg
    assert "hubspot" in msg or "search contacts" in msg
    assert "slack" in msg or "post message" in msg
    assert "apollo" not in msg
    pending = out.get("pending_task") or {}
    assert pending.get("type") == "connector_orchestration"
    assert pending.get("status") == "awaiting_plan_confirm"

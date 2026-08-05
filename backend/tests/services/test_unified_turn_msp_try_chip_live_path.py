"""Exact AI Chat TRY chip → pack MSP enrich confirm (LIVE path order)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.pack_common_intent_defaults import (
    format_pack_common_msp_enrich_confirm_message,
    try_pack_common_msp_enrich_workflow_plan,
)

TRY_CHIP = (
    'Use Clay to enrich the existing Apollo contact list "MSP Prospects", '
    'then add those enriched contacts to the existing HubSpot static list "MSPs".'
)


@pytest.mark.asyncio
async def test_apply_unified_turn_live_try_chip_stages_draft_workflow_confirm():
    """Right behavior: draft-workflow approve-first, not 2× Search contacts."""
    from app.services.unified_turn_reasoning_service import (
        UnifiedTurnShadowResult,
        apply_unified_turn_live,
    )

    enrich = try_pack_common_msp_enrich_workflow_plan(
        TRY_CHIP,
        connected_integrations=["apollo", "clay", "hubspot"],
    )
    assert enrich is not None
    expected = format_pack_common_msp_enrich_confirm_message(enrich)

    shadow = UnifiedTurnShadowResult(
        outcome_kind="conversational_reply",
        user_message="I can help with that.",
        connected_integrations=["apollo", "clay", "hubspot"],
        model="test",
    )
    refreshed = {
        "pending_task": {
            "type": "create_workflow",
            "status": "awaiting_confirm",
            "params": dict(enrich),
        },
        "clarified_params": dict(enrich),
    }
    state = MagicMock()
    state.update_task_state = AsyncMock()
    state.get_task_state = AsyncMock(return_value=refreshed)

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
    ):
        out = await apply_unified_turn_live(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-try-msp",
            message=TRY_CHIP,
            task_state={},
            conversation_history=[],
            connected_integrations=["apollo", "clay", "hubspot"],
            client=MagicMock(),
            settings=settings,
        )

    assert out is not None
    assert out.get("stop_pipeline") is True
    assert out.get("dialogue_mode") == "confirm"
    assert "draft workflow" in (out.get("message") or "").lower()
    assert "search contacts" not in (out.get("message") or "").lower()
    assert "MSP Prospects" in (out.get("message") or "")
    assert "MSPs" in (out.get("message") or "")
    # Exact pack copy (modulo whitespace)
    assert expected.split("\n")[0] in (out.get("message") or "")
    pending = (out.get("pending_task") or {}).get("params") or {}
    assert pending.get("invoke_action") == "assistant.create_workflow"
    # F1 retrieve-before-generate stages via retrieve_plan_gate (same pack plan).
    assert pending.get("source") in {
        "pack_common_msp_enrich",
        "retrieve_plan_gate_msp_enrich",
    }

"""Tests for unified live Gmail intent clarify path."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.unified_turn_reasoning_service import (
    UnifiedTurnShadowResult,
    apply_unified_turn_live,
)


@pytest.mark.asyncio
async def test_apply_unified_live_clarifies_gmail_send_vs_batch_mismatch():
    settings = MagicMock(unified_turn_live_enabled=True, openai_api_key="sk-test")
    proposal = UnifiedTurnShadowResult(
        outcome_kind="connector_tool_proposal",
        tool_name="gmail_messages_batch",
        tool_invoke_action="gmail.messages.batch",
        tool_arguments={"message_ids": ["x"]},
        requires_write_approval=True,
        connected_integrations=["gmail"],
    )

    with patch(
        "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
        new=AsyncMock(return_value=proposal),
    ), patch(
        "app.services.unified_turn_reasoning_service.emit_unified_turn_shadow_audit",
    ):
        out = await apply_unified_turn_live(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message='Send email to demo@example.com with subject "Hi" and body "Test"',
            task_state={},
            conversation_history=[],
            connected_integrations=["gmail"],
            settings=settings,
        )

    assert out is not None
    assert out["dialogue_mode"] == "clarify"
    assert "Send email" in out["message"]
    assert "Batch modify" in out["message"]


@pytest.mark.asyncio
async def test_apply_unified_live_incomplete_gmail_send_awaits_params_not_confirm():
    """Claude/Manus bar: incomplete send must clarify subject/body — not blind yes."""
    settings = MagicMock(unified_turn_live_enabled=True, openai_api_key="sk-test")
    proposal = UnifiedTurnShadowResult(
        outcome_kind="connector_tool_proposal",
        tool_name="gmail_messages_send",
        tool_invoke_action="gmail.messages.send",
        tool_arguments={
            "to": "stephaniekhan2002@gmail.com",
            "subject": "",
            "body": "",
            "contact_id": "19f9adfb88016f36",
        },
        requires_write_approval=True,
        connected_integrations=["gmail"],
    )
    plan = ConnectorActionPlan(
        tool_name="gmail_messages_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send email",
        args={
            "to": "stephaniekhan2002@gmail.com",
            "subject": "",
            "body": "",
            "contact_id": "19f9adfb88016f36",
        },
        requires_approval=True,
    )
    state = MagicMock()
    state.update_task_state = AsyncMock()
    state.get_task_state = AsyncMock(
        return_value={
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_params",
                "params": {
                    "invoke_action": "gmail.messages.send",
                    "args": {"to": "stephaniekhan2002@gmail.com"},
                },
            }
        }
    )

    with patch(
        "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
        new=AsyncMock(return_value=proposal),
    ), patch(
        "app.services.unified_turn_reasoning_service.emit_unified_turn_shadow_audit",
    ), patch(
        "app.services.react_write_gate.plan_from_react_tool_call",
        return_value=plan,
    ), patch(
        "app.services.tool_registry.get_tool_registry",
        return_value=MagicMock(),
    ), patch(
        "app.services.conversation_state_service.get_conversation_state_service",
        return_value=state,
    ), patch(
        "app.services.connector_parameter_inference.infer_missing_parameters",
        side_effect=lambda p, _ctx: p,
    ):
        out = await apply_unified_turn_live(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message="send an email to stephanie",
            task_state={},
            conversation_history=[],
            connected_integrations=["gmail"],
            settings=settings,
        )

    assert out is not None
    assert out["dialogue_mode"] == "clarify"
    assert out["unified_outcome_kind"] == "clarifying_question"
    assert "reply **yes**" not in (out["message"] or "").lower()
    assert "reply yes" not in (out["message"] or "").lower()
    saved = state.update_task_state.await_args.args[2]
    assert saved["pending_task"]["status"] == "awaiting_params"
    missing_hint = (out["message"] or "").lower()
    assert "subject" in missing_hint or "body" in missing_hint

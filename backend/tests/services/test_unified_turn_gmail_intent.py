"""Tests for unified live Gmail intent clarify path."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

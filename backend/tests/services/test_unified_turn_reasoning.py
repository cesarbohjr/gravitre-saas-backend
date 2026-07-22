"""Unified turn reasoning — shadow path and pending context."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.module_d_unified_voice_spec import (
    MODULE_D_UNIFIED_SYSTEM_SPEC,
    build_module_d_unified_system_prompt,
)
from app.services.unified_turn_pending_context import build_unified_turn_pending_context
from app.services.unified_turn_reasoning_service import (
    run_unified_turn_shadow,
)


def test_module_d_unified_spec_has_knowledge_boundary_and_drift():
    text = build_module_d_unified_system_prompt()
    assert "Knowledge boundaries" in text or "anti-fabrication" in text.lower()
    assert "NEVER state a specific number" in MODULE_D_UNIFIED_SYSTEM_SPEC
    assert "drift" in text.lower()
    assert "hold" in text.lower() and "abandon" in text.lower()
    assert "vendor.resource.verb" in text or "catalog" in text.lower()


def test_build_unified_turn_pending_context_empty_when_no_pending():
    assert build_unified_turn_pending_context({}) == ""
    assert build_unified_turn_pending_context(None) == ""


def test_build_unified_turn_pending_context_awaiting_params():
    state = {
        "pending_task": {
            "status": "awaiting_params",
            "type": "connector_action",
            "params": {
                "label": "Send message",
                "integration": "gmail",
                "invoke_action": "gmail.messages.send",
            },
        },
        "parameter_ledger": {
            "pending_missing": ["subject", "to"],
        },
    }
    text = build_unified_turn_pending_context(state, last_assistant_message="What subject?")
    assert "awaiting_params" in text
    assert "gmail.messages.send" not in text
    assert "Still needed" in text
    assert "What subject?" in text


@pytest.mark.asyncio
async def test_run_unified_turn_shadow_skipped_when_disabled():
    result = await run_unified_turn_shadow(
        org_id="org",
        user_id="user",
        conversation_id="conv",
        message="hey",
        task_state={},
        conversation_history=[],
        connected_integrations=["gmail"],
        settings=MagicMock(unified_turn_shadow_enabled=False),
    )
    assert result.outcome_kind == "skipped"


@pytest.mark.asyncio
async def test_run_unified_turn_shadow_conversational_reply():
    mock_choice = MagicMock()
    mock_choice.message.content = "You're welcome — what should we tackle next?"
    mock_choice.message.tool_calls = []
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    mock_router = MagicMock()
    mock_router._openai = mock_client

    settings = MagicMock(
        unified_turn_shadow_enabled=True,
        unified_turn_shadow_max_tools=24,
        openai_api_key="sk-test",
    )

    with patch("app.services.unified_turn_reasoning_service.get_tool_registry") as reg_patch, patch(
        "app.services.unified_turn_reasoning_service.get_model_router",
        return_value=mock_router,
    ), patch(
        "app.services.unified_turn_reasoning_service.narrow_tools_for_turn",
        return_value=([], {"visibleTools": 0}),
    ):
        reg_patch.return_value.get_tools_for_agent.return_value = []
        result = await run_unified_turn_shadow(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message="thanks!",
            task_state={},
            conversation_history=[],
            connected_integrations=["gmail"],
            settings=settings,
        )

    assert result.outcome_kind in {"conversational_reply", "clarifying_question"}
    assert "gmail." not in result.user_message
    mock_client.chat.completions.create.assert_awaited_once()
    call_kwargs = mock_client.chat.completions.create.await_args.kwargs
    system = call_kwargs["messages"][0]["content"]
    assert "NEVER state a specific number" in system
    assert "AVAILABLE TOOLS THIS TURN" in call_kwargs["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_run_unified_turn_shadow_knowledge_boundary_kind():
    mock_choice = MagicMock()
    mock_choice.message.content = (
        "I don't have that count yet — run history was not retrieved this turn. "
        "I can fetch it with the workflow runs tool if you want."
    )
    mock_choice.message.tool_calls = []
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_router = MagicMock()
    mock_router._openai = mock_client
    settings = MagicMock(
        unified_turn_shadow_enabled=True,
        unified_turn_shadow_max_tools=24,
        openai_api_key="sk-test",
    )

    with patch("app.services.unified_turn_reasoning_service.get_tool_registry") as reg_patch, patch(
        "app.services.unified_turn_reasoning_service.get_model_router",
        return_value=mock_router,
    ), patch(
        "app.services.unified_turn_reasoning_service.narrow_tools_for_turn",
        return_value=([], {"visibleTools": 0}),
    ):
        reg_patch.return_value.get_tools_for_agent.return_value = []
        result = await run_unified_turn_shadow(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message="how many workflow runs happened this week?",
            task_state={},
            conversation_history=[],
            connected_integrations=[],
            settings=settings,
        )

    assert result.outcome_kind == "knowledge_boundary"
    assert "0 recent" not in result.user_message.lower()


@pytest.mark.asyncio
async def test_run_unified_turn_shadow_tool_proposal():
    mock_tc = MagicMock()
    mock_tc.function.name = "gmail_messages_send"
    mock_tc.function.arguments = '{"to":"a@b.com","subject":"Hi","body":"Hello"}'
    mock_choice = MagicMock()
    mock_choice.message.content = ""
    mock_choice.message.tool_calls = [mock_tc]
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    mock_router = MagicMock()
    mock_router._openai = mock_client

    mock_spec = MagicMock(invoke_action="gmail.messages.send")
    mock_registry = MagicMock()
    mock_registry.get_tools_for_agent.return_value = []
    mock_registry._specs = {"gmail_messages_send": mock_spec}

    settings = MagicMock(
        unified_turn_shadow_enabled=True,
        unified_turn_shadow_max_tools=24,
        openai_api_key="sk-test",
    )

    with patch(
        "app.services.unified_turn_reasoning_service.get_tool_registry",
        return_value=mock_registry,
    ), patch(
        "app.services.unified_turn_reasoning_service.get_model_router",
        return_value=mock_router,
    ), patch(
        "app.services.unified_turn_reasoning_service.narrow_tools_for_turn",
        return_value=([{"type": "function"}], {"visibleTools": 1}),
    ), patch(
        "app.services.unified_turn_reasoning_service.tool_requires_user_write_approval",
        return_value=(True, "write", "gmail"),
    ):
        result = await run_unified_turn_shadow(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message="send that email now",
            task_state={},
            conversation_history=[],
            connected_integrations=["gmail"],
            settings=settings,
        )

    assert result.outcome_kind == "connector_tool_proposal"
    assert result.tool_name == "gmail_messages_send"
    assert result.requires_write_approval is True
    assert result.tool_arguments.get("to") == "a@b.com"

"""Unified turn reasoning — shadow path and pending context."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.module_d_unified_voice_spec import (
    MODULE_D_UNIFIED_SYSTEM_SPEC,
    build_module_d_unified_system_prompt,
)
from app.services.unified_turn_pending_context import build_unified_turn_pending_context
from app.services.unified_turn_reasoning_service import (
    UnifiedTurnShadowResult,
    apply_unified_turn_live,
    run_unified_turn_shadow,
    schedule_unified_turn_shadow,
)


def _mock_stream_client(*, content: str = "", tool_calls: list | None = None) -> MagicMock:
    """OpenAI client mock that returns a stream of deltas (Phase 3 TTFT path)."""

    async def _stream(**kwargs):
        assert kwargs.get("stream") is True

        async def _gen():
            if content:
                # Two deltas so TTFT != full completion latency in real runs.
                mid = max(1, len(content) // 2)
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=content[:mid], tool_calls=None))]
                )
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=content[mid:], tool_calls=None))]
                )
            for idx, tc in enumerate(tool_calls or []):
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        index=idx,
                                        id=f"call_{idx}",
                                        function=SimpleNamespace(
                                            name=tc.function.name,
                                            arguments=tc.function.arguments,
                                        ),
                                    )
                                ],
                            )
                        )
                    ]
                )

        return _gen()

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=_stream)
    return mock_client


def test_module_d_unified_spec_has_knowledge_boundary_and_drift():
    text = build_module_d_unified_system_prompt()
    assert "Knowledge boundaries" in text or "anti-fabrication" in text.lower()
    assert "NEVER state a specific number" in MODULE_D_UNIFIED_SYSTEM_SPEC
    assert "drift" in text.lower()
    assert "hold" in text.lower() and "abandon" in text.lower()
    assert "vendor.resource.verb" in text or "catalog" in text.lower()
    assert "Imperfect input" in MODULE_D_UNIFIED_SYSTEM_SPEC
    assert "I think you meant" in MODULE_D_UNIFIED_SYSTEM_SPEC
    assert "sned emial" in text.lower()


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
        settings=MagicMock(
            unified_turn_shadow_enabled=False,
            unified_turn_live_enabled=False,
        ),
    )
    assert result.outcome_kind == "skipped"


@pytest.mark.asyncio
async def test_apply_unified_turn_live_serves_conversational_text():
    mock_client = _mock_stream_client(content="Hey — here when you need me.")
    mock_router = MagicMock()
    mock_router._openai = mock_client
    settings = MagicMock(
        unified_turn_shadow_enabled=False,
        unified_turn_live_enabled=True,
        unified_turn_shadow_max_tools=24,
        unified_turn_embedding_tool_retrieval=False,
        unified_turn_task_max_tools=16,
        unified_turn_task_model_tier="",
        openai_api_key="sk-test",
    )
    with patch("app.services.unified_turn_reasoning_service.get_tool_registry") as reg_patch, patch(
        "app.services.unified_turn_reasoning_service.get_model_router",
        return_value=mock_router,
    ), patch(
        "app.services.unified_turn_reasoning_service.narrow_tools_for_turn",
        return_value=([], {"visibleTools": 0}),
    ), patch(
        "app.services.unified_turn_reasoning_service.emit_unified_turn_shadow_audit"
    ) as audit:
        reg_patch.return_value.get_tools_for_agent.return_value = []
        turn = await apply_unified_turn_live(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message="hey",
            task_state={},
            conversation_history=[],
            connected_integrations=["gmail"],
            client=MagicMock(),
            settings=settings,
            mode_key="fast",
        )
    assert turn is not None
    assert turn["stop_pipeline"] is True
    assert "Hey" in turn["message"]
    assert turn["unified_outcome_kind"] == "conversational_reply"
    audit.assert_called_once()
    assert audit.call_args.kwargs["result"].live_served is True


def test_schedule_unified_turn_shadow_noop_when_live_enabled():
    with patch(
        "app.services.unified_turn_reasoning_service.asyncio.get_running_loop"
    ) as loop_patch:
        schedule_unified_turn_shadow(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message="hey",
            task_state={},
            conversation_history=[],
            connected_integrations=[],
            settings=MagicMock(
                unified_turn_shadow_enabled=True,
                unified_turn_live_enabled=True,
            ),
        )
    loop_patch.assert_not_called()


@pytest.mark.asyncio
async def test_run_unified_turn_shadow_conversational_reply():
    mock_client = _mock_stream_client(content="You're welcome — what should we tackle next?")
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
    assert result.streamed is True
    assert result.first_token_proxy_ms is not None
    assert result.latency_breakdown.get("retrieval_method") == "keyword_narrow_tools_for_turn"
    assert result.latency_breakdown.get("embedding_tool_retrieval") is False
    assert "model_ttft_ms" in result.latency_breakdown
    assert "pre_model_ms" in result.latency_breakdown
    mock_client.chat.completions.create.assert_awaited_once()
    call_kwargs = mock_client.chat.completions.create.await_args.kwargs
    assert call_kwargs.get("stream") is True
    system = call_kwargs["messages"][0]["content"]
    assert "NEVER state a specific number" in system
    assert "AVAILABLE TOOLS THIS TURN" in call_kwargs["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_run_unified_turn_shadow_knowledge_boundary_kind():
    mock_client = _mock_stream_client(
        content=(
            "I don't have that count yet — run history was not retrieved this turn. "
            "I can fetch it with the workflow runs tool if you want."
        )
    )
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
    mock_tc = SimpleNamespace(
        function=SimpleNamespace(
            name="gmail_messages_send",
            arguments='{"to":"a@b.com","subject":"Hi","body":"Hello"}',
        )
    )
    mock_client = _mock_stream_client(tool_calls=[mock_tc])
    mock_router = MagicMock()
    mock_router._openai = mock_client

    mock_spec = MagicMock(invoke_action="gmail.messages.send")
    mock_registry = MagicMock()
    mock_registry.get_tools_for_agent.return_value = []
    mock_registry._specs = {"gmail_messages_send": mock_spec}

    settings = MagicMock(
        unified_turn_shadow_enabled=True,
        unified_turn_shadow_max_tools=24,
        unified_turn_embedding_tool_retrieval=False,
        unified_turn_task_max_tools=16,
        unified_turn_task_model_tier="",
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


@pytest.mark.asyncio
async def test_apply_unified_live_pending_unrelated_uses_hold_prompt():
    state = {
        "pending_task": {
            "status": "awaiting_params",
            "type": "connector_action",
            "params": {"label": "Send Gmail message", "integration": "gmail"},
        },
        "parameter_ledger": {"pending_missing": ["recipient", "body"]},
    }
    settings = MagicMock(unified_turn_live_enabled=True, openai_api_key="sk-test")

    with patch(
        "app.services.unified_turn_pending_live.classify_pending_reply",
        new=AsyncMock(return_value="unrelated"),
    ), patch(
        "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
        new=AsyncMock(),
    ) as mock_shadow, patch(
        "app.services.unified_turn_reasoning_service.emit_unified_turn_shadow_audit",
    ):
        out = await apply_unified_turn_live(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message="what connectors are Connected right now?",
            task_state=state,
            conversation_history=[],
            connected_integrations=["apollo"],
            settings=settings,
        )

    mock_shadow.assert_not_called()
    assert out is not None
    assert out["stop_pipeline"] is True
    assert "abandon" in out["message"].lower()
    assert "hold" in out["message"].lower()
    assert "Send Gmail message" in out["message"]


@pytest.mark.asyncio
async def test_apply_unified_live_meta_capability_uses_expression_path():
    settings = MagicMock(unified_turn_live_enabled=True, openai_api_key="sk-test")
    meta_text = (
        "I am Gravitree — a calm operator for your Connected tools. Connected for this org right now: Apollo."
    )

    with patch(
        "app.services.conversational_reply_service.generate_conversational_reply",
        new=AsyncMock(return_value=meta_text),
    ), patch(
        "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
        new=AsyncMock(),
    ) as mock_shadow:
        out = await apply_unified_turn_live(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message="what can you do?",
            task_state={},
            conversation_history=[],
            connected_integrations=["apollo"],
            settings=settings,
        )

    mock_shadow.assert_not_called()
    assert out is not None
    assert "Connected tools" in out["message"]


@pytest.mark.asyncio
async def test_apply_unified_live_prepends_mixed_social_ack():
    settings = MagicMock(unified_turn_live_enabled=True, openai_api_key="sk-test")
    body = UnifiedTurnShadowResult(
        outcome_kind="conversational_reply",
        user_message="HubSpot isn't Connected here. Connect it at /connectors.",
    )

    with patch(
        "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
        new=AsyncMock(return_value=body),
    ), patch(
        "app.services.unified_turn_reasoning_service.emit_unified_turn_shadow_audit",
    ), patch(
        "app.services.conversational_turn_gate.classify_turn_shape",
        new=AsyncMock(
            return_value=SimpleNamespace(
                shape="mixed",
                social_portion="haha nice",
                task_portion="check that HubSpot list",
                category="banter",
            )
        ),
    ), patch(
        "app.services.conversational_reply_service.generate_social_ack",
        new=AsyncMock(return_value="Ha — noted."),
    ):
        out = await apply_unified_turn_live(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message="haha nice, also can you check on that HubSpot list",
            task_state={},
            conversation_history=[],
            connected_integrations=["apollo"],
            settings=settings,
            mode_key="fast",
        )

    assert out is not None
    assert out["message"].startswith("Ha — noted.")
    assert "HubSpot" in out["message"]


@pytest.mark.asyncio
async def test_apply_unified_live_rejects_phantom_hold_abandon():
    settings = MagicMock(unified_turn_live_enabled=True, openai_api_key="sk-test")
    bad = UnifiedTurnShadowResult(
        outcome_kind="clarifying_question",
        user_message=(
            "You have a pending item that isn't finished. Should I **abandon** it "
            "and check on the HubSpot list, or **hold** it aside? Reply `abandon` or `hold`."
        ),
    )

    with patch(
        "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
        new=AsyncMock(return_value=bad),
    ), patch(
        "app.services.unified_turn_reasoning_service.emit_unified_turn_shadow_audit",
    ):
        out = await apply_unified_turn_live(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message="haha nice, also check that HubSpot list",
            task_state={},
            conversation_history=[],
            connected_integrations=["hubspot"],
            settings=settings,
        )

    assert out is None

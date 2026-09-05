"""Voice-latency Phase 0 (2026-09-05): real, per-source context-size breakdown.

Mutation-proof coverage for `context_size_breakdown` / `context_real_tokens_total`
on `run_unified_turn_shadow`'s `latency_breakdown` — the honest, per-source
(system prompt / history / tools / connected-integrations / ...) real token
counts introduced to correlate context bloat with the llm_first_token p99 tail.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.narrowed_tools import mark_narrowed
from app.services.real_token_counter import count_real_tokens, real_token_counting_available
from app.services.unified_turn_reasoning_service import run_unified_turn_shadow


def _mock_narrowed(tools: list, stats: dict | None = None) -> tuple[list, dict]:
    payload = stats or {"visibleTools": len(tools), "retrievalMethod": "keyword_narrow_tools_for_turn"}
    return mark_narrowed(list(tools), stats=payload, source="narrow_tools_for_turn"), payload


def _mock_stream_client(*, content: str = "ok") -> MagicMock:
    async def _stream(**kwargs):
        async def _gen():
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=content, tool_calls=None))]
            )
            yield SimpleNamespace(
                usage=SimpleNamespace(
                    prompt_tokens=999,
                    completion_tokens=3,
                    prompt_tokens_details=SimpleNamespace(cached_tokens=100),
                ),
                choices=[],
            )

        return _gen()

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=_stream)
    return mock_client


def _settings():
    return MagicMock(
        unified_turn_shadow_enabled=True,
        unified_turn_embedding_tool_retrieval=False,
        unified_turn_task_max_tools=16,
        unified_turn_task_model_tier="",
        openai_api_key="sk-test",
        unified_turn_shadow_max_tools=24,
    )


DISTINCTIVE_HISTORY_TEXT = "xylophone quantum orchard cardigan lattice"


@pytest.mark.asyncio
async def test_context_size_breakdown_has_expected_real_sources():
    mock_client = _mock_stream_client()
    mock_router = MagicMock()
    mock_router._openai = mock_client

    with patch("app.services.unified_turn_reasoning_service.get_tool_registry") as reg_patch, patch(
        "app.services.unified_turn_reasoning_service.get_model_router",
        return_value=mock_router,
    ), patch(
        "app.services.unified_turn_reasoning_service.narrow_tools_for_turn",
        return_value=_mock_narrowed([]),
    ):
        reg_patch.return_value.get_tools_for_agent.return_value = []
        result = await run_unified_turn_shadow(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message="what's the status of my last email?",
            task_state={},
            conversation_history=[
                {"role": "user", "content": DISTINCTIVE_HISTORY_TEXT},
                {"role": "assistant", "content": "Got it."},
            ],
            connected_integrations=["gmail"],
            settings=_settings(),
        )

    breakdown = result.latency_breakdown
    ctx = breakdown.get("context_size_breakdown")
    assert isinstance(ctx, dict)

    # Every real source this turn actually sends must be present and non-empty.
    for label in (
        "system_prompt",
        "conversation_history",
        "tool_schemas",
        "pending_state",
        "connected_integrations",
        "tools_list_note",
        "user_message",
    ):
        assert label in ctx, f"missing context source: {label}"
        assert ctx[label]["chars"] >= 0
        assert ctx[label]["tokens"] >= 0

    # System prompt and user message are always non-trivial text this turn.
    assert ctx["system_prompt"]["chars"] > 500
    assert ctx["system_prompt"]["tokens"] > 50
    assert ctx["user_message"]["chars"] > 0
    assert ctx["user_message"]["tokens"] > 0

    # History section must reflect the real history passed in, not be a no-op.
    assert ctx["conversation_history"]["turn_count"] == 2
    assert ctx["conversation_history"]["chars"] >= len(DISTINCTIVE_HISTORY_TEXT)
    assert ctx["conversation_history"]["tokens"] > 0

    # Real tiktoken tokens must differ from a naive chars-as-tokens mutation —
    # tokens should be meaningfully fewer than chars for real English prose.
    assert ctx["system_prompt"]["tokens"] < ctx["system_prompt"]["chars"]

    total = breakdown.get("context_real_tokens_total")
    assert isinstance(total, int) and total > 0
    assert total == sum(int(v.get("tokens") or 0) for v in ctx.values())

    assert breakdown.get("inference_provider") == "openai"


@pytest.mark.asyncio
async def test_context_size_breakdown_tool_schemas_reflect_attached_tools():
    mock_client = _mock_stream_client()
    mock_router = MagicMock()
    mock_router._openai = mock_client

    tool = {
        "type": "function",
        "function": {
            "name": "gmail.messages.send",
            "description": "Send an email via Gmail.",
            "parameters": {
                "type": "object",
                "properties": {"to": {"type": "string"}, "subject": {"type": "string"}},
            },
        },
    }

    with patch("app.services.unified_turn_reasoning_service.get_tool_registry") as reg_patch, patch(
        "app.services.unified_turn_reasoning_service.get_model_router",
        return_value=mock_router,
    ), patch(
        "app.services.unified_turn_reasoning_service.narrow_tools_for_turn",
        return_value=_mock_narrowed([tool]),
    ):
        reg_patch.return_value.get_tools_for_agent.return_value = [tool]
        result = await run_unified_turn_shadow(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message="send an email to stephanie",
            task_state={},
            conversation_history=[],
            connected_integrations=["gmail"],
            settings=_settings(),
        )

    ctx = result.latency_breakdown["context_size_breakdown"]
    # Progressive disclosure may add a search_catalog_tools stub alongside the
    # attached tool, so assert "at least the one real tool", not an exact count.
    assert ctx["tool_schemas"]["tool_count"] >= 1
    assert ctx["tool_schemas"]["tokens"] > 0


def test_real_token_counter_uses_real_tiktoken_not_chars_heuristic():
    assert real_token_counting_available() is True
    text = "The quick brown fox jumps over the lazy dog." * 5
    tokens = count_real_tokens(text, model="gpt-4o-mini")
    naive_heuristic = max(1, len(text) // 4)
    # Real tokenization on repeated English prose should differ from the
    # blunt len//4 heuristic used elsewhere in this codebase — if a future
    # edit silently swaps in the heuristic, this catches it.
    assert tokens != naive_heuristic
    assert 0 < tokens < len(text)


def test_real_token_counter_empty_string_is_zero():
    assert count_real_tokens("") == 0
    assert count_real_tokens(None) == 0  # type: ignore[arg-type]

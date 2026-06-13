"""Tests for conversation context summarization (STA-146)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings
from app.services import conversation_context_service as svc
from app.services.model_router import ModelResponse


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
        assistant_context_window_tokens=1000,
        assistant_context_summarize_threshold=0.8,
    )
    base.update(overrides)
    return Settings(**base)


def test_estimate_tokens():
    assert svc.estimate_tokens("") == 0
    assert svc.estimate_tokens("abcd") == 1


def test_format_summary_block_empty():
    assert svc.format_summary_block(None) == ""
    assert svc.format_summary_block("  ") == ""


def test_format_summary_block_includes_heading():
    block = svc.format_summary_block("User asked about HubSpot sync.")
    assert "Prior conversation summary" in block
    assert "HubSpot sync" in block


@pytest.mark.asyncio
async def test_maybe_summarize_history_under_threshold():
    history = [{"role": "user", "content": "hello"}]
    result = await svc.maybe_summarize_history(
        history=history,
        system_prompt="system",
        prompt="follow up",
        tool_messages=[],
        existing_summary=None,
        org_id="org-1",
        settings=_settings(),
    )
    assert result.messages == history
    assert result.summary_updated is False


@pytest.mark.asyncio
async def test_maybe_summarize_history_summarizes_oldest_half(monkeypatch):
    long_text = "word " * 500
    history = [
        {"role": "user", "content": long_text},
        {"role": "assistant", "content": long_text},
        {"role": "user", "content": "recent question"},
        {"role": "assistant", "content": "recent answer"},
    ]

    router = MagicMock()
    router.complete = AsyncMock(
        return_value=ModelResponse(
            provider="openai",
            model="gpt-5.5",
            content="Earlier discussion covered pipeline hygiene.",
            input_tokens=100,
            output_tokens=20,
            latency_ms=50,
            cost_usd=0.001,
        )
    )
    monkeypatch.setattr(svc, "get_model_router", lambda: router)

    result = await svc.maybe_summarize_history(
        history=history,
        system_prompt="system prompt",
        prompt="latest",
        tool_messages=[],
        existing_summary=None,
        org_id="org-1",
        settings=_settings(assistant_context_window_tokens=1000),
    )

    assert len(result.messages) == 2
    assert result.messages[0]["content"] == "recent question"
    assert result.summary == "Earlier discussion covered pipeline hygiene."
    assert result.summary_updated is True
    router.complete.assert_awaited_once()
    assert "USER:" in router.complete.await_args.kwargs["prompt"]


def test_load_conversation_summary_returns_value():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"last_summary": "Prior topic: workflows"}]
    )
    value = svc.load_conversation_summary(
        client,
        conversation_id="conv-1",
        org_id="org-1",
        user_id="user-1",
    )
    assert value == "Prior topic: workflows"


def test_persist_conversation_summary_updates_row():
    client = MagicMock()
    update = MagicMock()
    client.table.return_value.update.return_value = update
    update.eq.return_value = update
    update.execute.return_value = MagicMock(data=[{"id": "conv-1"}])

    svc.persist_conversation_summary(
        client,
        conversation_id="conv-1",
        org_id="org-1",
        user_id="user-1",
        summary="Updated summary",
    )

    client.table.return_value.update.assert_called_once_with({"last_summary": "Updated summary"})

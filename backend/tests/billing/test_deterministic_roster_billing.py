"""A roster assembled without a model must not generate estimated AI credits."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.routers.assistant as assistant
import app.services.response_composer as composer
from app.config import Settings


@pytest.mark.asyncio
async def test_deterministic_roster_is_not_billed_as_a_model_call(monkeypatch):
    billing = AsyncMock()
    query_record = AsyncMock()
    monkeypatch.setattr(assistant, "_record_assistant_billing", billing)
    monkeypatch.setattr(assistant, "get_supabase_client", lambda _settings: MagicMock())
    monkeypatch.setattr(assistant, "_persist_conversation_turn", lambda *a, **kw: None)
    monkeypatch.setattr(assistant, "_remember_completed_turn", lambda **kw: None)
    monkeypatch.setattr(assistant, "get_user_intelligence_service",
                        lambda: SimpleNamespace(record_query=query_record))
    monkeypatch.setattr(composer, "compose_reply_events", AsyncMock(
        return_value=composer.ComposerPacked(text="Three active agents", text_id="reply")))

    stream = assistant._build_stream(
        None, {}, settings=Settings(), org_id="org-1", user_id="user-1",
        conversation_id="conversation-1", user_text="How many agents?", agent_id=None,
        history_messages=[], existing_summary=None, mode="fast",
        intelligence_hub_deterministic_answer="Three active agents",
    )
    lines = []
    while True:
        try:
            # Mirrors voice silence ticks, which pull successive events from
            # different tasks rather than one long-lived request task.
            lines.append(await asyncio.create_task(anext(stream)))
        except StopAsyncIteration:
            break
    await asyncio.sleep(0)

    assert lines
    billing.assert_not_awaited()
    query_record.assert_awaited_once()

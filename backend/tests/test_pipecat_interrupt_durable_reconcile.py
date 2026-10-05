from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter


class _Query:
    def __init__(self, data):
        self.data = data
        self.updated = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def update(self, payload):
        self.updated = payload
        return self

    def execute(self):
        return MagicMock(data=self.data)


@pytest.mark.asyncio
async def test_interrupted_history_rewrites_latest_assistant_to_heard_prefix(monkeypatch):
    owned = _Query([{"id": "conv-1"}])
    latest = _Query([{"id": "msg-a"}])
    updated = _Query([{"id": "msg-a"}])

    class _Client:
        def table(self, name):
            if name == "conversations":
                return owned
            if updated.updated is not None:
                return updated
            # First conversation_messages call is the lookup; after update()
            # the same object records the payload.
            return latest

    client = _Client()
    # Make update observable on the lookup object itself.
    latest.update = lambda payload: (setattr(latest, "updated", payload) or latest)

    monkeypatch.setattr(
        "app.workflows.repository.get_supabase_client",
        lambda _settings: client,
    )

    reporter = ElevenLabsInterruptReporter(
        settings=object(),
        org_id="org-1",
        user_id="user-1",
        conversation_id="conv-1",
    )
    await reporter._persist_interrupted_assistant_text("I heard this part.")

    assert latest.updated == {"content": "I heard this part."}


@pytest.mark.asyncio
async def test_interrupted_history_requires_owned_conversation(monkeypatch):
    owned = _Query([])

    class _Client:
        def table(self, _name):
            return owned

    monkeypatch.setattr(
        "app.workflows.repository.get_supabase_client",
        lambda _settings: _Client(),
    )

    reporter = ElevenLabsInterruptReporter(
        settings=object(),
        org_id="org-1",
        user_id="user-1",
        conversation_id="conv-1",
    )
    await reporter._persist_interrupted_assistant_text("prefix")
    assert owned.updated is None

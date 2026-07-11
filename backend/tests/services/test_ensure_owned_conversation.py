"""STA-306 — ensure conversations row before mid-stream task_state writes."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.conversation_state_service import ConversationStateService, DEFAULT_TASK_STATE


@pytest.mark.asyncio
async def test_ensure_owned_conversation_inserts_when_missing():
    service = ConversationStateService()
    insert_payloads: list[dict] = []

    class _FakeTable:
        def __init__(self, name: str):
            self.name = name
            self._filters: dict = {}

        def select(self, *_a, **_k):
            return self

        def eq(self, key, value):
            self._filters[key] = value
            return self

        def limit(self, *_a, **_k):
            return self

        def insert(self, payload):
            insert_payloads.append(payload)
            return self

        def execute(self):
            if self.name == "conversations" and insert_payloads and "id" in (insert_payloads[-1] or {}):
                return MagicMock(data=[insert_payloads[-1]], error=None)
            # select path: no row
            return MagicMock(data=[], error=None)

    client = MagicMock()
    client.table = lambda name: _FakeTable(name)

    out = await service.ensure_owned_conversation(
        org_id="org-1",
        user_id="user-1",
        conversation_id="11111111-1111-1111-1111-111111111111",
        title="Create Apollo list",
        client=client,
    )
    assert out == "11111111-1111-1111-1111-111111111111"
    assert insert_payloads
    assert insert_payloads[0]["id"] == "11111111-1111-1111-1111-111111111111"
    assert insert_payloads[0]["org_id"] == "org-1"
    assert insert_payloads[0]["user_id"] == "user-1"
    assert insert_payloads[0]["task_state"] == DEFAULT_TASK_STATE


@pytest.mark.asyncio
async def test_ensure_owned_conversation_skips_insert_when_owned():
    service = ConversationStateService()
    inserts = []

    class _FakeTable:
        def select(self, *_a, **_k):
            return self

        def eq(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        def insert(self, payload):
            inserts.append(payload)
            return self

        def execute(self):
            return MagicMock(data=[{"id": "conv-existing"}], error=None)

    client = MagicMock()
    client.table = lambda _name: _FakeTable()

    out = await service.ensure_owned_conversation(
        org_id="org-1",
        user_id="user-1",
        conversation_id="conv-existing",
        client=client,
    )
    assert out == "conv-existing"
    assert inserts == []


def test_resolve_keeps_fast_when_connectors_connected_still():
    from app.operators.assistant_mode_config import resolve_effective_intelligence_mode

    assert resolve_effective_intelligence_mode("fast", ["apollo", "hubspot"]) == "fast"

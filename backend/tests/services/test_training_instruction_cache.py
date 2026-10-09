"""Custom instruction texts are cached per org and dropped on every write.

Every chat turn's system prompt reads them, so the read is cached for the
shared production client only; writes invalidate the org.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.services import training_service
from app.services.training_service import (
    invalidate_instruction_cache,
    load_active_instruction_texts,
)


class _Client:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.reads = 0


@pytest.fixture(autouse=True)
def _fresh_cache():
    training_service._instruction_cache.clear()
    yield
    training_service._instruction_cache.clear()


def _patched(client: _Client, *, shared: bool):
    def _execute_or_empty(_client: Any, _builder: Any, *, resource: str) -> list[dict[str, Any]]:
        client.reads += 1
        return list(client.rows)

    class _Builder:
        def __getattr__(self, _name: str) -> Any:
            return lambda *a, **k: self

    return (
        patch.object(training_service, "execute_or_empty", side_effect=_execute_or_empty),
        patch("app.core.org_state_cache.cache_allowed", return_value=shared),
        patch.object(_Client, "table", lambda self, _name: _Builder(), create=True),
    )


def _load(client: _Client) -> list[str]:
    return load_active_instruction_texts(client, "org-1", agent_id=None)


def test_shared_client_reads_once_until_invalidated() -> None:
    client = _Client([{"name": "Tone", "content": "Be brief."}])
    a, b, c = _patched(client, shared=True)
    with a, b, c:
        assert _load(client) == ["Tone: Be brief."]
        assert _load(client) == ["Tone: Be brief."]
        assert client.reads == 1
        client.rows = [{"name": "Tone", "content": "Be warm."}]
        invalidate_instruction_cache("org-1")
        assert _load(client) == ["Tone: Be warm."]
        assert client.reads == 2


def test_other_clients_are_never_cached() -> None:
    client = _Client([{"name": "Tone", "content": "Be brief."}])
    a, b, c = _patched(client, shared=False)
    with a, b, c:
        _load(client)
        _load(client)
    assert client.reads == 2


def test_invalidate_ignores_blank_org() -> None:
    invalidate_instruction_cache(None)
    invalidate_instruction_cache("  ")

"""One turn asks for the same question's primary entity several times at once."""
from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.knowledge_graph_service import KnowledgeGraphService


def _router(calls: list[str], content: str):
    async def _complete(*_args, **kwargs):
        calls.append(kwargs.get("org_id"))
        await asyncio.sleep(0.02)
        return SimpleNamespace(content=content)

    return SimpleNamespace(complete=_complete)


@pytest.mark.asyncio
async def test_concurrent_and_repeated_asks_share_one_lookup(mock_settings):
    calls: list[str] = []
    client = MagicMock()
    with patch("app.services.graph_query_intent.resolve_entity_from_knowledge_nodes", return_value=None), patch(
        "app.services.knowledge_graph_service.get_model_router",
        return_value=_router(calls, '{"entity_type": "company", "entity_id": "acme"}'),
    ):
        svc = KnowledgeGraphService()
        results = await asyncio.gather(
            *(svc._identify_primary_entity("org-1", "how is acme doing", settings=mock_settings, client=client) for _ in range(4))
        )
        again = await svc._identify_primary_entity("org-1", "how is acme doing", settings=mock_settings, client=client)
        await svc._identify_primary_entity("org-2", "how is acme doing", settings=mock_settings, client=client)
    assert calls == ["org-1", "org-2"]  # one per org, never shared across orgs
    assert all(r["entity_id"] == "acme" for r in results) and again["entity_id"] == "acme"
    results[0]["entity_id"] = "mutated"
    assert again["entity_id"] == "acme"  # callers get their own copy


@pytest.mark.asyncio
async def test_unknown_answer_is_not_kept(mock_settings):
    calls: list[str] = []
    with patch("app.services.graph_query_intent.resolve_entity_from_knowledge_nodes", return_value=None), patch(
        "app.services.knowledge_graph_service.get_model_router", return_value=_router(calls, "not json")
    ):
        svc = KnowledgeGraphService()
        for _ in range(2):
            out = await svc._identify_primary_entity("org-1", "hmm", settings=mock_settings, client=MagicMock())
            assert out["entity_type"] == "unknown"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_knowledge_node_read_runs_off_the_event_loop(mock_settings):
    loop_thread = threading.current_thread()
    seen: list[threading.Thread] = []

    def _resolve(org_id, question, *, client):
        seen.append(threading.current_thread())
        return {"entity_type": "company", "entity_id": "n1", "display_name": "Acme"}

    with patch("app.services.graph_query_intent.resolve_entity_from_knowledge_nodes", side_effect=_resolve):
        out = await KnowledgeGraphService()._identify_primary_entity(
            "org-1", "acme", settings=mock_settings, client=MagicMock()
        )
    assert out["resolution"] == "org_knowledge_nodes"
    assert seen and seen[0] is not loop_thread

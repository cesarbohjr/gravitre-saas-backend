from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.agent_memory_service import (
    _memory_retrieval_enabled,
    build_task_retrieval_context,
    create_agent_memory,
    delete_agent_memory,
    format_retrieval_prompt_section,
    list_agent_memories,
    update_agent_memory,
)


def _table_chain(data):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.ilike.return_value = chain
    chain.limit.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    chain.execute.return_value = MagicMock(data=data)
    return chain


def _client_by_table(tables: dict[str, list]) -> tuple[MagicMock, dict[str, MagicMock]]:
    """Dispatch ``client.table(name)`` by name rather than call order.

    An ordered ``side_effect`` list ties the test to how many reads the function
    happens to make. When department sharing added two more (agents again, then
    departments), the two-entry list ran out and raised StopIteration -- a
    failure that pointed at the mock, not at the feature that changed.
    """
    chains = {name: _table_chain(rows) for name, rows in tables.items()}
    client = MagicMock()
    client.table.side_effect = lambda name, *args, **kwargs: chains[name]
    return client, chains


def test_memory_retrieval_enabled_from_config():
    agent = {"id": "a1", "config": {"use_memory": True}}
    assert _memory_retrieval_enabled(agent, {}) is True
    assert _memory_retrieval_enabled(agent, {"include_agent_memory": False}) is False


def test_format_retrieval_prompt_section_empty():
    assert format_retrieval_prompt_section({"memories": [], "rag_chunks": []}) == ""


def test_format_retrieval_prompt_section_includes_payload():
    section = format_retrieval_prompt_section({"memories": [{"content": "ICP is SaaS"}], "rag_chunks": []})
    assert section.startswith("<agent_memory_context>")
    assert "ICP is SaaS" in section


def test_list_agent_memories_returns_rows():
    org_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    client = MagicMock()
    client.table.side_effect = [
        _table_chain([{"id": agent_id, "org_id": org_id, "name": "Atlas", "department": "Marketing", "config": {}}]),
        _table_chain([
            {
                "id": str(uuid.uuid4()),
                "agent_id": agent_id,
                "content": "Primary ICP is SaaS",
                "category": "fact",
                "provenance": "Training",
                "confidence": 95,
                "usage_count": 2,
                "editable": True,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ]),
    ]
    rows = list_agent_memories(client, org_id, agent_id)
    assert len(rows) == 1
    assert rows[0]["content"] == "Primary ICP is SaaS"
    assert rows[0]["usageCount"] == 2


@patch("app.services.agent_memory_service.get_embedding", return_value=[0.1, 0.2])
def test_create_agent_memory_inserts_embedding(mock_embed):
    org_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    memory_id = str(uuid.uuid4())
    department_id = str(uuid.uuid4())
    client, chains = _client_by_table(
        {
            "agents": [
                {
                    "id": agent_id,
                    "org_id": org_id,
                    "name": "Atlas",
                    "department": "Marketing",
                    "config": {},
                }
            ],
            "departments": [{"id": department_id}],
            "agent_memories": [
                {
                    "id": memory_id,
                    "agent_id": agent_id,
                    "content": "Always be concise",
                    "category": "preference",
                    "provenance": "Manual",
                    "confidence": 90,
                    "usage_count": 0,
                    "editable": True,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            ],
        }
    )
    settings = MagicMock()
    row = create_agent_memory(
        settings,
        client,
        org_id,
        agent_id,
        user_id="user-1",
        content="Always be concise",
        category="preference",
        provenance="Manual",
    )
    assert row["category"] == "preference"
    mock_embed.assert_called_once()

    payload = chains["agent_memories"].insert.call_args.args[0]
    assert payload["embedding"] == [0.1, 0.2]
    assert payload["created_by"] == "user-1"
    # share_with_department defaults True, so the resolved department must land on
    # the row -- the behavior whose two extra reads broke the old ordered mock.
    assert payload["department_id"] == department_id


def test_delete_protected_memory_forbidden():
    org_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    memory_id = str(uuid.uuid4())
    client = MagicMock()
    client.table.side_effect = [
        _table_chain([{"id": agent_id, "org_id": org_id, "name": "Atlas", "department": "Marketing", "config": {}}]),
        _table_chain([
            {
                "id": memory_id,
                "agent_id": agent_id,
                "content": "Compliance rule",
                "category": "rule",
                "provenance": "Compliance",
                "confidence": 100,
                "usage_count": 0,
                "editable": False,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ]),
    ]
    with pytest.raises(HTTPException) as exc:
        delete_agent_memory(client, org_id, agent_id, memory_id)
    assert exc.value.status_code == 403


@patch("app.services.agent_memory_service.search_agent_memories", return_value=[{"content": "ICP"}])
def test_build_task_retrieval_context_when_enabled(mock_search):
    settings = MagicMock()
    client = MagicMock()
    agent = {"id": "agent-1", "config": {"use_memory": True}}
    context = build_task_retrieval_context(
        settings,
        client,
        org_id="org-1",
        agent=agent,
        task="Qualify this lead",
    )
    assert context["memories"] == [{"content": "ICP"}]
    mock_search.assert_called_once()


@patch("app.services.agent_memory_service.get_embedding", return_value=[0.1, 0.2])
def test_update_agent_memory_rejects_empty_content(mock_embed):
    org_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    memory_id = str(uuid.uuid4())
    client = MagicMock()
    client.table.side_effect = [
        _table_chain([{"id": agent_id, "org_id": org_id, "name": "Atlas", "department": "Marketing", "config": {}}]),
        _table_chain([
            {
                "id": memory_id,
                "agent_id": agent_id,
                "content": "Existing",
                "category": "fact",
                "provenance": "Manual",
                "confidence": 90,
                "usage_count": 0,
                "editable": True,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ]),
    ]
    settings = MagicMock()
    with pytest.raises(HTTPException) as exc:
        update_agent_memory(settings, client, org_id, agent_id, memory_id, content="   ")
    assert exc.value.status_code == 400

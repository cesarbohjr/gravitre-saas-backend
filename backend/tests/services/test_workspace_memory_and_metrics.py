"""Unit tests for Part 1 items 1–3 helpers (workspace memory, metrics defaults)."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.cognitive_metrics import (
    PLATFORM_METRIC_DEFAULTS,
    list_platform_defaults,
    resolve_metric,
)
from app.services.org_knowledge_nodes_service import VALID_NODE_TYPES, create_knowledge_node
from app.services.workspace_memory_service import (
    TYPED_CATEGORIES,
    extract_typed_memories_from_act,
    promote_turn_memories,
    recall_workspace,
)


def _chainable(data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.insert.return_value = mock
    mock.execute.return_value = MagicMock(data=data or [], error=None)
    return mock


def test_platform_defaults_include_mql_cac_arr():
    defaults = list_platform_defaults()
    keys = {d["metric_key"] for d in defaults}
    assert keys == {"mql", "cac", "arr"}
    assert PLATFORM_METRIC_DEFAULTS["mql"]["formula"] == "count(leads where marketing_qualified=true)"
    assert PLATFORM_METRIC_DEFAULTS["cac"]["formula"] == "(sales_spend + marketing_spend) / new_customers"
    assert PLATFORM_METRIC_DEFAULTS["arr"]["formula"] == "sum(mrr) * 12"


def test_resolve_metric_prefers_org_override():
    client = MagicMock()
    table = _chainable(
        [
            {
                "id": "def-1",
                "org_id": "org-1",
                "metric_key": "mql",
                "label": "Org MQL",
                "formula": "count(custom)",
                "source_system": "hubspot",
                "owner": "revops",
            }
        ]
    )
    client.table.return_value = table
    resolved = resolve_metric(client, "org-1", "mql")
    assert resolved["resolved_from"] == "org_metric_definitions"
    assert resolved["definition_id"] == "def-1"
    assert resolved["formula"] == "count(custom)"


def test_resolve_metric_falls_back_to_platform_default():
    client = MagicMock()
    table = _chainable([])
    client.table.return_value = table
    resolved = resolve_metric(client, "org-1", "cac")
    assert resolved["resolved_from"] == "platform_default"
    assert resolved["definition_id"] is None
    assert "sales_spend" in (resolved["formula"] or "")


def test_typed_categories_cover_cognitive_taxonomy():
    assert TYPED_CATEGORIES == {
        "decision",
        "outcome",
        "relationship",
        "procedural",
        "preference",
        "episodic",
    }


def test_promote_turn_memories_writes_org_scoped_rows():
    client = MagicMock()
    table = _chainable(
        [
            {
                "id": "m1",
                "org_id": "org-1",
                "agent_id": None,
                "category": "decision",
                "content": "Use HubSpot",
            }
        ]
    )
    client.table.return_value = table
    written = promote_turn_memories(
        client,
        org_id="org-1",
        memories=[{"content": "Use HubSpot", "category": "decision"}],
        agent_id=None,
        conversation_id="convo-a",
    )
    assert len(written) == 1
    client.table.assert_called_with("agent_memories")
    insert_payload = table.insert.call_args[0][0]
    assert insert_payload["org_id"] == "org-1"
    assert insert_payload["agent_id"] is None
    assert insert_payload["category"] == "decision"


def test_recall_workspace_filters_foreign_org():
    client = MagicMock()
    table = _chainable(
        [
            {
                "id": "m1",
                "org_id": "org-1",
                "category": "preference",
                "content": "prefer email",
                "confidence": 90,
            },
            {
                "id": "m2",
                "org_id": "org-foreign",
                "category": "preference",
                "content": "prefer email",
                "confidence": 90,
            },
        ]
    )
    client.table.return_value = table
    rows = recall_workspace(client, org_id="org-1", query="email", categories=["preference"])
    assert all(str(r.get("org_id")) == "org-1" for r in rows)


def test_extract_typed_memories_from_act():
    memories = extract_typed_memories_from_act(
        {
            "confirmed": True,
            "typed_memories": [{"content": "Decide X", "category": "decision"}],
        },
        outcome_event="workflow_executed",
        message="ran workflow",
    )
    assert any(m.get("category") == "decision" for m in memories)
    assert any(m.get("category") == "outcome" for m in memories)


def test_create_knowledge_node_validates_type():
    client = MagicMock()
    table = _chainable([{"id": "n1", "org_id": "org-1", "node_type": "company", "name": "Acme"}])
    client.table.return_value = table
    row = create_knowledge_node(client, "org-1", node_type="company", name="Acme")
    assert row is not None
    assert "company" in VALID_NODE_TYPES

"""Graph relationship query intent + entity resolution."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.graph_query_intent import (
    extract_relationship_topic_keywords,
    is_relationship_traversal_query,
    rank_paths_for_topic,
    resolve_entity_from_knowledge_nodes,
)


def test_relationship_query_detection():
    assert is_relationship_traversal_query(
        "How is Acme related to our Q3 pipeline decline?"
    )
    assert not is_relationship_traversal_query("What is Acme's billing address?")


def test_topic_keyword_extraction():
    kws = extract_relationship_topic_keywords("How is Acme related to our Q3 pipeline decline?")
    assert "acme" in kws
    assert "q3" in kws
    assert "pipeline" in kws


def test_resolve_acme_from_knowledge_nodes():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"id": "node-acme", "node_type": "company", "name": "Acme Corp"},
        {"id": "node-other", "node_type": "vendor", "name": "Other LLC"},
    ]
    resolved = resolve_entity_from_knowledge_nodes(
        "org-1",
        "How is Acme related to our Q3 pipeline decline?",
        client=client,
    )
    assert resolved is not None
    assert resolved["entity_id"] == "node-acme"
    assert resolved["entity_type"] == "company"


def test_rank_paths_prefers_pipeline_topic():
    paths = [
        {"entityType": "campaign", "entityId": "c1", "confidence": 0.9, "pathSummary": "company -[impacts]-> campaign"},
        {
            "entityType": "kpi",
            "entityId": "k1",
            "confidence": 0.7,
            "pathSummary": "company -[contributes_to]-> kpi pipeline q3",
        },
    ]
    ranked = rank_paths_for_topic(paths, ["pipeline", "q3"])
    assert ranked[0]["entityId"] == "k1"

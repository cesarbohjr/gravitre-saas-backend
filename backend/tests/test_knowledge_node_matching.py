"""Tests for knowledge node fuzzy matching (Learning 4.0 Phase 6)."""
from app.services.knowledge_node_matching import (
    find_knowledge_node_matches,
    score_name_match,
)


def test_score_name_match_exact_prefix_substring() -> None:
    assert score_name_match("Acme Corp", "Acme Corp") == 100
    assert score_name_match("Acme", "Acme Corporation") == 80
    assert score_name_match("Corporation", "Acme Corporation") == 60
    assert score_name_match("Totally Different", "Acme Corp") == 0


def test_find_knowledge_node_matches_respects_type_and_limit() -> None:
    rows = [
        {"id": "n1", "node_type": "customer", "name": "Acme Corp"},
        {"id": "n2", "node_type": "company", "name": "Acme Corporation"},
        {"id": "n3", "node_type": "customer", "name": "Other LLC"},
    ]
    matches = find_knowledge_node_matches(rows, "Acme", node_type="customer", min_score=60, limit=2)
    assert len(matches) == 1
    assert matches[0]["id"] == "n1"
    assert matches[0]["matchScore"] == 80
    assert matches[0]["source"] == "confirmed_knowledge"

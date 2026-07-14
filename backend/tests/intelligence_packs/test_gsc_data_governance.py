"""Unit tests: GSC Memory/KG stop-line (raw query strings gated)."""
from __future__ import annotations

import pytest

from app.intelligence_packs.shared.gsc_data_governance import (
    GscGovernanceError,
    annotate_gsc_tool_result,
    assert_gsc_safe_for_memory_kg,
    payload_contains_gsc_raw_queries,
    sanitize_gsc_payload_for_memory_kg,
)


def test_page_aggregates_are_memory_kg_eligible():
    payload = {
        "dimensions": ["page"],
        "rows": [{"page": "https://example.com/", "clicks": 10, "impressions": 100}],
    }
    assert payload_contains_gsc_raw_queries(payload) is False
    assert_gsc_safe_for_memory_kg(payload)
    annotated = annotate_gsc_tool_result(payload)
    assert annotated["memoryKgEligible"] is True
    assert annotated["includes_raw_queries"] is False


def test_raw_query_dimension_blocked_from_memory_kg():
    payload = {
        "dimensions": ["query"],
        "rows": [{"query": "cesar bohorquez", "clicks": 1, "impressions": 5}],
    }
    assert payload_contains_gsc_raw_queries(payload) is True
    with pytest.raises(GscGovernanceError) as exc:
        assert_gsc_safe_for_memory_kg(payload)
    assert exc.value.code == "GSC_RAW_QUERY_MEMORY_KG_BLOCKED"
    annotated = annotate_gsc_tool_result(payload)
    assert annotated["memoryKgEligible"] is False
    assert annotated["includes_raw_queries"] is True


def test_sanitize_strips_query_dimension():
    payload = {
        "dimensions": ["query", "page"],
        "rows": [
            {
                "query": "someone name",
                "page": "https://example.com/about",
                "clicks": 2,
                "impressions": 9,
            }
        ],
    }
    cleaned = sanitize_gsc_payload_for_memory_kg(payload)
    assert "query" not in cleaned["dimensions"]
    assert cleaned["includes_raw_queries"] is False
    assert_gsc_safe_for_memory_kg(cleaned)

"""Canonical route policy tests."""
from app.services.learning_strategy_keys import (
    build_cluster_segment_key,
    is_cluster_segment,
    parse_base_segment_key_from_segment,
)


def test_cluster_segment_roundtrip():
    segment = build_cluster_segment_key("abc", {"department": "ops", "intent": "analytics"})
    assert is_cluster_segment(segment)
    assert parse_base_segment_key_from_segment(segment) == "ops:analytics"

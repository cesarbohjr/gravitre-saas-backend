"""Revision-keyed ActionSpec cache."""
from __future__ import annotations

from app.connectors.action_catalog.registry import (
    clear_action_spec_cache,
    get_action_spec,
)


def test_get_action_spec_cached_returns_same_revision() -> None:
    clear_action_spec_cache()
    spec_a = get_action_spec("hubspot.deals.search")
    spec_b = get_action_spec("hubspot.deals.search")
    assert spec_a is not None
    assert spec_b is not None
    assert spec_a.id == spec_b.id
    assert spec_a.spec_revision == spec_b.spec_revision
    assert spec_a is spec_b


def test_clear_action_spec_cache() -> None:
    clear_action_spec_cache()
    first = get_action_spec("google_analytics.reports.run")
    clear_action_spec_cache()
    second = get_action_spec("google_analytics.reports.run")
    assert first is not None
    assert second is not None
    assert first.spec_revision == second.spec_revision

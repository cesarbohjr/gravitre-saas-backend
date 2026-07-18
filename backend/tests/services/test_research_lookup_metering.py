"""Tests for research lookup metering."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.research_lookup_metering import (
    estimate_internal_cogs_usd,
    included_lookups_for_plan_code,
    record_research_lookup,
)


def test_included_lookups_by_tier():
    assert included_lookups_for_plan_code("node") == 10
    assert included_lookups_for_plan_code("control") == 60
    assert included_lookups_for_plan_code("command") == 200


def test_estimate_internal_cogs_free_tier_grounding():
    cogs = estimate_internal_cogs_usd(grounding_count=1, input_tokens=500, output_tokens=100)
    assert cogs["grounding_cogs_usd"] == 0.0
    assert cogs["grounding_count"] == 1
    assert cogs["total_cogs_usd"] >= 0


def test_record_research_lookup_inserts(monkeypatch):
    client = MagicMock()
    table = MagicMock()
    client.table.return_value = table
    upsert = MagicMock()
    upsert.execute.return_value = MagicMock(data=[{"id": "1"}])
    table.upsert.return_value = upsert
    select = MagicMock()
    select.eq.return_value = select
    select.gte.return_value = select
    select.execute.return_value = MagicMock(data=[{"quantity": 1}])
    table.select.return_value = select

    monkeypatch.setattr(
        "app.services.research_lookup_metering.get_plan_for_org",
        lambda _c, _o: {"code": "node"},
    )

    result = record_research_lookup(
        client,
        org_id="org-1",
        provider="google_grounding",
        query_hash="abc123",
    )
    assert result["plan_code"] == "node"
    assert result["included_lookups_per_month"] == 10

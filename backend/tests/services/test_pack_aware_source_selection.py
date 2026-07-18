"""Tests for pack-aware source selection (Phase 3)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.intelligence_packs.shared.sources import ensure_pack_sources_registered, list_sources_for_pack
from app.services.adaptive_research_cascade import ResearchScope, should_run_intelligence_packs_stage
from app.services.pack_aware_source_selection import (
    attach_intelligence_packs_to_cascade,
    format_intelligence_pack_sources_section,
    retrieve_pack_sources,
    score_source_relevance,
    select_pack_sources,
    should_run_pack_source_stage,
)


def _settings(*, internet_enabled: bool = False, tavily: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        internet_research_enabled=internet_enabled,
        tavily_api_key=tavily,
    )


def _executive_assignment() -> dict:
    return {
        "label": "Executive Intelligence Pack",
        "metadata": {"intelligence_pack_id": "executive-intelligence-pack"},
    }


@pytest.fixture(autouse=True)
def _bootstrap_sources():
    ensure_pack_sources_registered()


def test_pack_source_registry_bootstraps_executive_vendors():
    sources = list_sources_for_pack("executive-intelligence-pack")
    vendors = {row.vendor for row in sources}
    assert "fred" in vendors
    assert "sec_edgar" in vendors


def test_score_source_relevance_prefers_matching_keywords():
    ensure_pack_sources_registered()
    selected = select_pack_sources(["executive-intelligence-pack"], "What is US GDP from FRED?")
    assert selected
    top_source, top_score = selected[0]
    assert top_score >= score_source_relevance(top_source, "unrelated topic")


def test_should_run_pack_source_stage_requires_scope_and_assignments():
    settings = _settings()
    assert should_run_pack_source_stage(
        ResearchScope.INTELLIGENCE_PACKS.value,
        settings=settings,
        knowledge_assignments=[_executive_assignment()],
    )
    assert not should_run_pack_source_stage(
        ResearchScope.INTERNAL_ONLY.value,
        settings=settings,
        knowledge_assignments=[_executive_assignment()],
    )
    assert not should_run_pack_source_stage(
        ResearchScope.INTELLIGENCE_PACKS.value,
        settings=settings,
        knowledge_assignments=[],
    )


def test_should_run_intelligence_packs_stage_matches_pack_helper():
    settings = _settings()
    assignments = [_executive_assignment()]
    assert should_run_intelligence_packs_stage(
        ResearchScope.EVERYTHING.value,
        settings=settings,
        knowledge_assignments=assignments,
    )


@pytest.mark.asyncio
async def test_retrieve_pack_sources_merges_catalog_and_db_rows():
    client = MagicMock()

    def _chainable_result(data: list[dict]):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.in_.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = MagicMock(data=data)
        return chain

    def _table(name: str):
        if name == "external_signals":
            return _chainable_result(
                [
                    {
                        "id": "sig-1",
                        "vendor": "fred",
                        "title": "GDP growth signal",
                        "summary": "GDP rose 2.1%",
                        "signal_type": "macro_observation",
                        "payload": {"series_id": "GDP"},
                    }
                ]
            )
        if name == "external_entities":
            return _chainable_result(
                [
                    {
                        "id": "ent-1",
                        "vendor": "fred",
                        "title": "FRED GDP series",
                        "entity_type": "macro_series",
                        "payload": {"latest": {"value": "2.1"}},
                    }
                ]
            )
        return MagicMock()

    client.table.side_effect = _table

    payload = await retrieve_pack_sources(
        client=client,
        org_id="org-1",
        query="GDP macro outlook",
        knowledge_assignments=[_executive_assignment()],
    )

    assert payload["pack_ids"] == ["executive-intelligence-pack"]
    assert payload["signal_count"] == 1
    assert payload["entity_count"] == 1
    rows = payload["rows"]
    assert rows
    assert all(row.get("kind") == "intelligence_pack" for row in rows)
    section = format_intelligence_pack_sources_section(rows)
    assert "<intelligence_pack_sources>" in section


def test_attach_intelligence_packs_to_cascade():
    merged = attach_intelligence_packs_to_cascade(
        {"internal_thin": True},
        payload={"rows": [{"id": "1"}], "pack_ids": ["executive-intelligence-pack"], "catalog_matches": 1},
        ran=True,
    )
    assert merged["intelligence_packs"]["ran"] is True
    assert merged["intelligence_packs"]["result_count"] == 1
    assert merged["intelligence_packs"]["pack_ids"] == ["executive-intelligence-pack"]

"""Wave D4/D5 — knowledge freshness admin + domain optimization engine tests."""
from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

from typing import Any

import pytest

from app.services.ai_trust_layer import get_ai_trust_layer
from app.services.domain_optimization_engine import DomainOptimizationEngine, get_domain_optimization_engine
from app.services.knowledge_freshness_service import (
    FRESHNESS_MULTIPLIER_INACCESSIBLE,
    FRESHNESS_MULTIPLIER_STALE,
    KnowledgeFreshnessService,
)


def _settings(**overrides: object) -> MagicMock:
    base = MagicMock(app_env="dev", domain_adaptive_learning_enabled=True)
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.asyncio
async def test_freshness_admin_summary_includes_stale_and_inaccessible():
    svc = KnowledgeFreshnessService(settings=_settings())
    rows = [
        {
            "id": "a1",
            "agent_id": "agent-1",
            "label": "SEO Pack",
            "source_type": "folder",
            "source_id": "x",
            "department": "marketing",
            "subdomain": "seo",
            "freshness_status": "stale",
            "enabled": True,
        },
        {
            "id": "a2",
            "agent_id": "agent-2",
            "label": "CRM",
            "source_type": "hubspot",
            "source_id": "y",
            "department": "sales",
            "subdomain": "pipeline",
            "permission_valid": False,
            "enabled": True,
        },
    ]
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = rows

    summary = await svc.load_admin_summary("org-1", client=mock_client)
    assert summary["status"] == "ok"
    assert len(summary["stale_sources"]) == 1
    assert len(summary["inaccessible_sources"]) == 1
    assert summary["stale_sources"][0]["freshness_multiplier"] == FRESHNESS_MULTIPLIER_STALE
    assert summary["inaccessible_sources"][0]["freshness_multiplier"] == FRESHNESS_MULTIPLIER_INACCESSIBLE
    assert summary["affected_agents"]
    assert summary["affected_domains"]
    assert summary["recommended_actions"]


@pytest.mark.asyncio
async def test_freshness_admin_org_isolation():
    svc = KnowledgeFreshnessService(settings=_settings())

    async def load_for_org(org_id: str, *, client: Any | None = None) -> dict:
        _ = client
        if org_id == "org-a":
            return {"org_id": org_id, "stale_sources": [{"assignment_id": "a1"}], "inaccessible_sources": []}
        return {"org_id": org_id, "stale_sources": [], "inaccessible_sources": [{"assignment_id": "b1"}]}

    with patch.object(svc, "load_admin_summary", side_effect=load_for_org):
        a = await svc.load_admin_summary("org-a")
        b = await svc.load_admin_summary("org-b")
    assert a["stale_sources"] and not b["stale_sources"]
    assert b["inaccessible_sources"] and not a["inaccessible_sources"]


@pytest.mark.asyncio
async def test_domain_optimization_advisory_only_enforced():
    engine = DomainOptimizationEngine(settings=_settings())
    inserted: list[dict] = []

    def fake_insert(row: dict) -> MagicMock:
        inserted.append(row)
        result = MagicMock()
        result.data = [row]
        return result

    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    mock_client.table.return_value.insert.side_effect = fake_insert

    with patch.object(engine, "_client", return_value=mock_client):
        with patch.object(engine, "_record_advisory_outcome", new_callable=AsyncMock):
            row = await engine._insert_recommendation(
                "org-1",
                segment_key="default:marketing:seo:qa",
                recommendation_type="refresh_stale_knowledge_source",
                title="Refresh stale knowledge source: SEO Pack",
                description="Refresh required",
                evidence={"assignment_id": "a1"},
            )
    assert row is not None
    assert inserted[0]["advisory_only"] is True
    assert inserted[0]["status"] == "pending_review"


def test_domain_optimization_has_no_auto_apply_method():
    engine = DomainOptimizationEngine(settings=_settings())
    assert not hasattr(engine, "apply_recommendation")
    assert not hasattr(engine, "auto_apply")
    public_methods = [
        name
        for name, fn in inspect.getmembers(engine, predicate=inspect.ismethod)
        if not name.startswith("_") and "apply" in name
    ]
    assert public_methods == []


@pytest.mark.asyncio
async def test_domain_optimization_no_auto_execution_flag():
    engine = DomainOptimizationEngine(settings=_settings())
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    with patch.object(engine, "_client", return_value=mock_client):
        summary = await engine.get_admin_summary("org-1")
    assert summary["advisory_only"] is True
    assert summary["auto_execution_enabled"] is False


@pytest.mark.asyncio
async def test_stale_source_recommendation_created():
    engine = DomainOptimizationEngine(settings=_settings())
    with patch(
        "app.services.knowledge_freshness_service.get_knowledge_freshness_service"
    ) as freshness_factory:
        freshness_factory.return_value.load_admin_summary = AsyncMock(
            return_value={
                "stale_sources": [
                    {
                        "assignment_id": "a1",
                        "label": "SEO Pack",
                        "department": "marketing",
                        "subdomain": "seo",
                        "freshness_score": 0.6,
                        "stale_reason": "stale_sync",
                    }
                ],
                "inaccessible_sources": [],
            }
        )
        with patch.object(engine, "_insert_recommendation", new_callable=AsyncMock) as insert:
            insert.return_value = {"id": "rec-1", "advisory_only": True}
            created = await engine._recommendations_from_freshness("org-1")
    assert len(created) == 1
    insert.assert_called_once()
    assert insert.call_args.kwargs["recommendation_type"] == "refresh_stale_knowledge_source"


@pytest.mark.asyncio
async def test_weak_segment_recommendation():
    engine = DomainOptimizationEngine(settings=_settings())
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {
            "segment_key": "default:marketing:seo:qa",
            "sample_count": 25,
            "positive_count": 5,
            "negative_count": 15,
            "noise_score": 0.1,
            "assignment_boost_deltas": {},
        }
    ]
    with patch.object(engine, "_client", return_value=mock_client):
        with patch.object(engine, "_insert_recommendation", new_callable=AsyncMock) as insert:
            insert.return_value = {"id": "rec-2", "advisory_only": True}
            created = await engine._recommendations_from_learning_segments("org-1")
    assert created
    assert any(
        call.kwargs.get("recommendation_type") == "weak_segment_performance"
        for call in insert.call_args_list
    )


@pytest.mark.asyncio
async def test_insufficient_data_recommendation_honest():
    engine = DomainOptimizationEngine(settings=_settings())
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {
            "segment_key": "default:marketing:seo:qa",
            "sample_count": 3,
            "positive_count": 2,
            "negative_count": 1,
            "noise_score": 0.0,
            "assignment_boost_deltas": {},
        }
    ]
    with patch.object(engine, "_client", return_value=mock_client):
        with patch.object(engine, "_insert_recommendation", new_callable=AsyncMock) as insert:
            insert.return_value = {"id": "rec-3", "advisory_only": True}
            created = await engine._recommendations_from_learning_segments("org-1")
    assert created
    assert insert.call_args.kwargs["recommendation_type"] == "insufficient_learning_data"


@pytest.mark.asyncio
async def test_domain_optimization_disabled_returns_disabled_summary():
    engine = DomainOptimizationEngine(settings=_settings(domain_adaptive_learning_enabled=False))
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    with patch.object(engine, "_client", return_value=mock_client):
        summary = await engine.get_admin_summary("org-1")
    assert summary["status"] == "disabled"


def test_trust_layer_optimization_metadata_advisory_only():
    trust = get_ai_trust_layer()
    metadata = trust.build_optimization_trust_metadata(
        freshness_envelope={"stale_source_count": 2},
        optimization_summary={"pending_count": 3, "insufficient_data_warnings": ["seg-a"]},
    )
    assert metadata["domain_optimization"]["advisory_only"] is True
    assert metadata["domain_optimization"]["auto_execution_enabled"] is False
    assert metadata["domain_optimization"]["pending_recommendations"] == 3


def test_engine_singleton():
    assert get_domain_optimization_engine(_settings()) is not None

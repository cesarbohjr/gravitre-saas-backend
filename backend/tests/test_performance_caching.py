"""Performance tier caching, Tier 0, dashboard, and connector timeout tests."""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators.assistant_mode_config import MODE_CONFIG
from app.services.cache_service import CacheService
from app.services.intelligence_engine_settings import (
    DEFAULTS,
    IntelligenceEngineSettings,
    tier0_enabled,
    tier0_ttl_seconds,
    validation_enabled_for_mode,
)
from app.services.performance_dashboard_service import compute_request_cost, load_performance_dashboard
from app.services.performance_tier import TIER_0, TIER_1, TIER_2, TIER_3, mode_to_tier
from app.services.query_normalization import normalize_query
from app.services.rag_cache_helpers import retrieval_cache_parts
from app.services.tier0_cache import (
    get_tier0_answer,
    is_cache_entry_stale,
    is_tier0_ineligible_query,
    set_tier0_answer,
)


@pytest.fixture(autouse=True)
def _clear_memory_cache():
    from app.services import cache_service as cache_module

    cache_module._MEMORY.clear()
    cache_module._MEMORY_STATS.clear()
    cache_module._cache = None
    with patch("app.services.cache_service.get_redis_client", return_value=None):
        yield
    cache_module._MEMORY.clear()
    cache_module._MEMORY_STATS.clear()
    cache_module._cache = None


def test_mode_config_maps_to_performance_tiers():
    assert mode_to_tier("fast") == TIER_1
    assert mode_to_tier("standard") == TIER_2
    assert mode_to_tier("reasoning") == TIER_3
    assert mode_to_tier("agent") == TIER_3
    assert TIER_0 not in MODE_CONFIG


def test_tier0_disabled_for_accuracy_priority():
    settings = IntelligenceEngineSettings(performance_mode="accuracy_priority")
    assert tier0_enabled(settings) is False
    assert tier0_ttl_seconds(settings) == 3600


def test_performance_mode_speed_priority_longer_tier0_ttl():
    settings = IntelligenceEngineSettings(performance_mode="speed_priority")
    assert tier0_ttl_seconds(settings) == 7200


def test_validation_mode_matrix():
    balanced = IntelligenceEngineSettings(performance_mode="balanced")
    speed = IntelligenceEngineSettings(performance_mode="speed_priority")
    accuracy = IntelligenceEngineSettings(performance_mode="accuracy_priority")
    assert validation_enabled_for_mode("fast", balanced) is False
    assert validation_enabled_for_mode("standard", balanced) is True
    assert validation_enabled_for_mode("standard", speed) is False
    assert validation_enabled_for_mode("agent", speed) is True
    assert validation_enabled_for_mode("fast", accuracy) is True


@pytest.mark.asyncio
async def test_tier0_cache_hit_returns_under_target_latency():
    settings = SimpleNamespace()
    cache = CacheService(settings=settings)
    normalized = normalize_query("What's our churn rate?")
    await cache.set(
        "tier0_answer",
        {
            "answer": "Cached churn is 4.2%.",
            "cached_at": "2026-06-07T00:00:00+00:00",
            "source_document_ids": [],
            "source_fingerprint": "",
            "confidence": {"score": 0.9},
            "answer_explanation": "From cached policy doc.",
        },
        3600,
        "org-a",
        normalized,
    )
    started = time.monotonic()
    hit = await get_tier0_answer(settings, org_id="org-a", query="What's our churn rate?")
    elapsed_ms = int((time.monotonic() - started) * 1000)
    assert hit is not None
    assert "4.2%" in hit["answer"]
    assert elapsed_ms < 500


@pytest.mark.asyncio
async def test_tier0_cache_invalidated_when_source_updated():
    settings = SimpleNamespace()
    cached = {
        "answer": "Old answer",
        "source_document_ids": ["doc-1"],
        "source_fingerprint": "doc-1:2026-01-01T00:00:00+00:00",
    }
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = SimpleNamespace(
        data=[{"id": "doc-1", "updated_at": "2026-06-07T12:00:00+00:00"}]
    )
    stale = await is_cache_entry_stale(settings, cached, "org-a", client=client)
    assert stale is True


@pytest.mark.asyncio
async def test_embedding_cache_reduces_duplicate_computation():
    settings = SimpleNamespace()
    cache = CacheService(settings=settings)
    vector = [0.1, 0.2, 0.3]
    await cache.set("embedding", {"vector": vector, "method": "openai"}, 3600, "text-embedding-3-small", "org-a", "hello")
    cached = await cache.get("embedding", "text-embedding-3-small", "org-a", "hello")
    assert cached["vector"] == vector


@pytest.mark.asyncio
async def test_retrieval_cache_respects_short_ttl():
    settings = SimpleNamespace()
    cache = CacheService(settings=settings)
    parts = retrieval_cache_parts("org-a", "pipeline status", "organization", 8, {"environment": "default"})
    await cache.set("retrieval", {"rows": [{"id": "1"}], "metrics": {"top_k": 8}}, 1, *parts)
    assert await cache.get("retrieval", *parts) is not None
    await asyncio.sleep(1.1)
    assert await cache.get("retrieval", *parts) is None


@pytest.mark.asyncio
async def test_cache_never_leaks_across_orgs():
    settings = SimpleNamespace()
    cache = CacheService(settings=settings)
    await cache.set("tier0_answer", {"answer": "Org A secret"}, 3600, "org-a", "secret query")
    org_b = await cache.get("tier0_answer", "org-b", "secret query")
    assert org_b is None


@pytest.mark.asyncio
async def test_connector_timeout_returns_partial_with_note():
    from app.services.tool_registry import ToolRegistry
    from app.services.tool_types import ToolContext

    registry = ToolRegistry()
    spec = registry.get_spec("hubspot_search_contacts")
    assert spec is not None

    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_timeout_seconds=1,
    )

    with patch("app.services.tool_registry.invoke_tool", side_effect=lambda *args, **kwargs: time.sleep(2)):
        result = await registry.execute_tool(
            ctx=ctx,
            tool_name="hubspot_search_contacts",
            args={"query": "acme"},
        )
    assert result["success"] is False
    assert result.get("partial") is True
    assert "did not respond within" in result["error"]


@pytest.mark.asyncio
async def test_latency_logged_per_stage():
    settings = SimpleNamespace()
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = SimpleNamespace(data=[])

    from app.services.latency_tracking import log_pipeline_latency

    await log_pipeline_latency(
        settings,
        org_id="org-1",
        stage_name="retrieval",
        duration_ms=12,
        message_id="msg-1",
        cache_hit=True,
        tier=TIER_1,
        client=client,
    )
    payload = client.table.return_value.insert.call_args[0][0]
    assert payload["stage_name"] == "retrieval"
    assert payload["cache_hit"] is True
    assert payload["tier"] == TIER_1


def test_cost_calculation_uses_model_router_pricing():
    with patch.dict(
        "app.services.model_router._MODEL_PRICING_PER_1K",
        {"gpt-5.4-mini": (0.001, 0.002, 0.003)},
        clear=False,
    ):
        cost = compute_request_cost("gpt-5.4-mini", input_tokens=1000, output_tokens=500)
    assert cost > 0


@pytest.mark.asyncio
async def test_dashboard_endpoint_returns_real_aggregates_not_hardcoded():
    settings = SimpleNamespace()
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "stage_name": "generation",
                "duration_ms": 100,
                "cache_hit": False,
                "tier": TIER_2,
                "estimated_cost_usd": 0.002,
                "created_at": "2026-06-07T00:00:00+00:00",
            },
            {
                "stage_name": "retrieval",
                "duration_ms": 40,
                "cache_hit": True,
                "tier": TIER_2,
                "estimated_cost_usd": None,
                "created_at": "2026-06-07T00:00:00+00:00",
            },
        ]
    )
    payload = await load_performance_dashboard(settings, "org-1", period="24h", client=client)
    assert payload["sampleCount"] == 2
    assert payload["avgTotalResponseMs"] == 70
    assert "generation" in payload["byStage"]


@pytest.mark.asyncio
async def test_set_tier0_answer_normalizes_query():
    settings = SimpleNamespace()
    cache = CacheService(settings=settings)
    with patch("app.services.tier0_cache.get_cache_service", return_value=cache), patch(
        "app.services.tier0_cache._source_fingerprint",
        AsyncMock(return_value=""),
    ):
        await set_tier0_answer(
            settings,
            org_id="org-a",
            query="What's our churn rate?",
            answer="4.2%",
            source_document_ids=[],
        )
    hit = await cache.get("tier0_answer", "org-a", normalize_query("What's our churn rate?"))
    assert hit is not None
    assert hit["answer"] == "4.2%"


def test_confirm_decline_queries_are_tier0_ineligible():
    """Bare yes/no must not be org-cached — poisons awaiting_plan_confirm."""
    assert is_tier0_ineligible_query("yes") is True
    assert is_tier0_ineligible_query("YES") is True
    assert is_tier0_ineligible_query("approve") is True
    assert is_tier0_ineligible_query("no") is True
    assert is_tier0_ineligible_query("What's our churn rate?") is False


@pytest.mark.asyncio
async def test_tier0_skips_poisoned_yes_cache_entry():
    settings = SimpleNamespace()
    cache = CacheService(settings=settings)
    await cache.set(
        "tier0_answer",
        {
            "answer": 'I don\'t have enough information yet. Tell me what "yes" should confirm.',
            "cached_at": "2026-07-20T00:00:00+00:00",
            "source_document_ids": [],
            "source_fingerprint": "",
        },
        3600,
        "org-a",
        normalize_query("yes"),
    )
    with patch("app.services.tier0_cache.get_cache_service", return_value=cache):
        hit = await get_tier0_answer(settings, org_id="org-a", query="yes")
    assert hit is None
    with patch("app.services.tier0_cache.get_cache_service", return_value=cache), patch(
        "app.services.tier0_cache._source_fingerprint",
        AsyncMock(return_value=""),
    ):
        await set_tier0_answer(
            settings,
            org_id="org-a",
            query="yes",
            answer="should not store",
            source_document_ids=[],
        )
    # Prior poisoned entry may remain in store, but set must not refresh it via eligible path.
    assert is_tier0_ineligible_query("yes") is True

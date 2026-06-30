"""Admin performance dashboard aggregates from ai_pipeline_latency + cache stats."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

from app.services.cache_service import get_cache_service
from app.services.performance_tier import TIER_0, TIER_1, TIER_2, TIER_3
from app.workflows.repository import get_supabase_client

PERIOD_HOURS = {"1h": 1, "24h": 24, "7d": 24 * 7}


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return int(ordered[index])


def _latency_stats(values: list[int]) -> dict[str, int]:
    if not values:
        return {"avg_ms": 0, "p50_ms": 0, "p95_ms": 0, "count": 0}
    return {
        "avg_ms": int(mean(values)),
        "p50_ms": _percentile(values, 50),
        "p95_ms": _percentile(values, 95),
        "count": len(values),
    }


async def load_performance_dashboard(
    settings: Any,
    org_id: str,
    *,
    period: str = "24h",
    client: Any | None = None,
) -> dict[str, Any]:
    hours = PERIOD_HOURS.get(period, 24)
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    db = client or get_supabase_client(settings)
    rows = (
        db.table("ai_pipeline_latency")
        .select("stage_name, duration_ms, cache_hit, tier, estimated_cost_usd, created_at")
        .eq("org_id", org_id)
        .gte("created_at", since)
        .execute()
        .data
        or []
    )

    by_stage: dict[str, list[int]] = {}
    by_tier: dict[str, list[int]] = {}
    costs: list[float] = []
    tier0_hits = 0
    tier0_total = 0

    for row in rows:
        stage = str(row.get("stage_name") or "unknown")
        duration = int(row.get("duration_ms") or 0)
        by_stage.setdefault(stage, []).append(duration)
        tier = str(row.get("tier") or TIER_2)
        by_tier.setdefault(tier, []).append(duration)
        if row.get("estimated_cost_usd") is not None:
            costs.append(float(row["estimated_cost_usd"]))
        if tier == TIER_0:
            tier0_total += 1
            if row.get("cache_hit"):
                tier0_hits += 1

    cache = get_cache_service(settings)
    cache_stats = {
        namespace: _cache_hit_rate(cache.stats(namespace))
        for namespace in ("tier0_answer", "embedding", "retrieval", "rerank", "source_summary")
    }
    timeout_stats = cache.stats("connector_timeout")
    timeout_count = int(timeout_stats.get("count") or 0)
    sample_count = len(rows)
    timeout_rate = round(timeout_count / max(1, sample_count), 4) if sample_count else 0.0

    all_durations = [value for values in by_stage.values() for value in values]
    total_stats = _latency_stats(all_durations)

    return {
        "period": period,
        "avgTotalResponseMs": total_stats["avg_ms"],
        "p50TotalResponseMs": total_stats["p50_ms"],
        "p95TotalResponseMs": total_stats["p95_ms"],
        "byStage": {
            stage: {
                "avgMs": stats["avg_ms"],
                "p50Ms": stats["p50_ms"],
                "p95Ms": stats["p95_ms"],
                "count": stats["count"],
            }
            for stage, stats in ((stage, _latency_stats(values)) for stage, values in by_stage.items())
        },
        "cacheHitRate": {
            "tier_0": _safe_rate(tier0_hits, tier0_total) if tier0_total else cache_stats.get("tier0_answer", 0.0),
            "embedding": cache_stats.get("embedding", 0.0),
            "retrieval": cache_stats.get("retrieval", 0.0),
            "rerank": cache_stats.get("rerank", 0.0),
            "source_summary": cache_stats.get("source_summary", 0.0),
        },
        "timeoutRate": timeout_rate,
        "avgCostPerAnswerUsd": round(sum(costs) / len(costs), 6) if costs else 0.0,
        "byTier": {
            tier: {
                "count": len(values),
                "avgMs": _latency_stats(values)["avg_ms"],
                "avgCost": round(
                    sum(float(r.get("estimated_cost_usd") or 0) for r in rows if str(r.get("tier") or "") == tier)
                    / max(1, sum(1 for r in rows if str(r.get("tier") or "") == tier)),
                    6,
                ),
            }
            for tier, values in {
                TIER_0: by_tier.get(TIER_0, []),
                TIER_1: by_tier.get(TIER_1, []),
                TIER_2: by_tier.get(TIER_2, []),
                TIER_3: by_tier.get(TIER_3, []),
            }.items()
        },
        "sampleCount": sample_count,
    }


def _cache_hit_rate(stats: dict[str, int]) -> float:
    total = int(stats.get("hit") or 0) + int(stats.get("miss") or 0)
    if total <= 0:
        return 0.0
    return round(int(stats.get("hit") or 0) / total, 4)


def _safe_rate(hits: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(hits / total, 4)


def compute_request_cost(model_used: str, input_tokens: int, output_tokens: int) -> float:
    from app.services.model_router import _MODEL_PRICING_PER_1K

    pricing = _MODEL_PRICING_PER_1K.get(model_used)
    if not pricing:
        return 0.0
    input_rate, _, output_rate = pricing
    return round((input_tokens * input_rate + output_tokens * output_rate) / 1000.0, 6)

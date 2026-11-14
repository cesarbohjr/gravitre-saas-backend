"""Opt-in, privacy-safe ECO-002 router timing. Never changes dispatch or decisions."""
from __future__ import annotations

import os
from time import perf_counter
from typing import Any, Awaitable, TypeVar

from prometheus_client import Histogram

from app.core.logging import get_logger

logger = get_logger(__name__)
T = TypeVar("T")

# Fixed stage names only: never use request text, organization IDs, or dynamic labels.
STAGES = frozenset({
    "overview_policy", "dialogue_settings", "understanding", "classification",
    "query_cluster", "clarification", "context_assembly", "risk_evaluation",
    "model_selection", "enrichments", "response_dispatch", "guidance",
})
ROUTE_STAGE_SECONDS = Histogram(
    "gravitre_intelligence_route_stage_duration_seconds",
    "Elapsed seconds for an ECO-002 intelligence routing stage",
    ("stage", "outcome"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)


def enabled() -> bool:
    return os.environ.get("ECO002_ROUTING_LATENCY_TRACE", "").strip().lower() in {"1", "true", "yes"}


async def measure(stage: str, task: Awaitable[T]) -> T:
    """Preserve await ordering, result and exceptions; measure only when opted in."""
    if not enabled():
        return await task
    if stage not in STAGES:
        raise ValueError("Unrecognized static ECO-002 routing stage")
    start = perf_counter()
    outcome = "error"
    try:
        value = await task
        outcome = "ok"
        return value
    finally:
        elapsed = max(0.0, perf_counter() - start)
        ROUTE_STAGE_SECONDS.labels(stage=stage, outcome=outcome).observe(elapsed)
        logger.info("eco002_route_stage stage=%s outcome=%s duration_ms=%.3f", stage, outcome, elapsed * 1000.0)

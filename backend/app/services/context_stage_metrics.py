"""Privacy-safe opt-in ECO-003 timing for isolated context/retrieval stages.

No caching, concurrency, request payloads or tenant-derived metric labels.
"""
from __future__ import annotations

import os
from time import perf_counter
from typing import Awaitable, TypeVar

from prometheus_client import Histogram

from app.core.logging import get_logger

logger = get_logger(__name__)
T = TypeVar("T")

STAGES = frozenset({
    "unified_retrieval",
    "org_context",
    "agent_memory",
    "rag_retrieval",
    "company_intelligence",
    "external_research",
})

CONTEXT_STAGE_SECONDS = Histogram(
    "gravitre_context_stage_duration_seconds",
    "Duration of a context retrieval stage in seconds",
    ("stage", "outcome"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)


def enabled() -> bool:
    return os.environ.get("ECO003_CONTEXT_LATENCY_TRACE", "").strip().lower() in {"1", "true", "yes"}


async def measure(stage: str, awaitable: Awaitable[T]) -> T:
    """Observe one await without changing ordering, exceptions or cancellation."""
    if not enabled():
        return await awaitable
    if stage not in STAGES:
        # Ensure supplied coroutine does not leak even for rejected instrumentation.
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()
        raise ValueError("Unrecognized static ECO-003 context stage")
    start = perf_counter()
    outcome = "error"
    try:
        result = await awaitable
        outcome = "ok"
        return result
    except BaseException:
        # CancelledError remains distinct and is always propagated.
        raise
    finally:
        elapsed = max(0.0, perf_counter() - start)
        CONTEXT_STAGE_SECONDS.labels(stage=stage, outcome=outcome).observe(elapsed)
        logger.info("eco003_context_stage stage=%s outcome=%s duration_ms=%.3f", stage, outcome, elapsed * 1000)

"""Opt-in, low-cardinality routing stage timing; never records request content.

The observer runs on both success and failure. Timing must never change the
routing result, mask an exception, or interfere with cancellation.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from contextlib import contextmanager
import os
from time import perf_counter
from typing import Awaitable, TypeVar

T = TypeVar("T")
_REQUEST_SAMPLE = ContextVar("eco002_request_sample", default=None)


@contextmanager
def router_sample(sample_id: str):
    """Bind a synthetic, non-identifying sample label for per-request traces."""
    if not sample_id or len(sample_id) > 48 or not all(c.isalnum() or c in '-_' for c in sample_id):
        raise ValueError("invalid synthetic sample identifier")
    token = _REQUEST_SAMPLE.set(sample_id)
    try:
        yield
    finally:
        _REQUEST_SAMPLE.reset(token)

_LOG = logging.getLogger(__name__)
_ALLOWED = frozenset({
    "overview_policy", "dialogue_settings", "understanding", "classification",
    "query_cluster", "clarification", "context", "risk_evaluation",
    "model_selection", "enrichments", "knowledge_response", "execution",
    "proactive_guidance", "decision_visibility",
})
_SURFACES = frozenset({"api", "chat", "voice", "agent", "play", "canvas"})


async def timed_router_stage(stage: str, surface: str, operation: Awaitable[T]) -> T:
    """Await unchanged; optionally emit a content-free stage duration in ms."""
    if os.getenv("GRAVITRE_ROUTER_STAGE_TIMING_ENABLED") != "1":
        return await operation
    if stage not in _ALLOWED:
        raise ValueError("Unknown routing timing stage")
    safe_surface = surface if surface in _SURFACES else "other"
    start = perf_counter()
    outcome = "ok"
    try:
        return await operation
    except BaseException:
        outcome = "error"
        raise
    finally:
        try:
            elapsed_ms = max(0.0, (perf_counter() - start) * 1000)
            sample_id = _REQUEST_SAMPLE.get()
            if sample_id is None:
                _LOG.info(
                    "router_stage_timing stage=%s surface=%s outcome=%s duration_ms=%.3f",
                    stage, safe_surface, outcome, elapsed_ms,
                )
            else:
                _LOG.info(
                    "router_stage_timing stage=%s surface=%s outcome=%s duration_ms=%.3f sample=%s",
                    stage, safe_surface, outcome, elapsed_ms, sample_id,
                )
        except Exception:
            # Observability is non-authoritative and must never break routing.
            pass

"""3.0-C realtime voice eval lanes — architecture comparison, not a prod swap.

A CURRENT CASCADE: Deepgram STT → canonical execute_task_streaming → ElevenLabs
B NATIVE REALTIME: speech/audio model → same Gravitre runtime for tools → audio
C HYBRID: realtime conversation frontend + deterministic tool/work backend

Production remains lane A until a named benchmark + Cesar approval.
Lane B must never invoke provider tools except through execute_task_streaming
(HMAC / approval / Composer).
"""
from __future__ import annotations

from typing import Any

LANE_A = "A_CASCADE"
LANE_B = "B_NATIVE_REALTIME"
LANE_C = "C_HYBRID"
PRODUCTION_LANE = LANE_A

BENCHMARK_DIMENSIONS = (
    "semantic_accuracy",
    "interruptions",
    "tool_correctness",
    "latency_metric_a",
    "latency_metric_b",
    "cost",
    "voice_naturalness",
    "traceability",
    "governance",
    "context_parity",
)


def resolve_eval_lane(settings: Any | None) -> str:
    raw = str(getattr(settings, "voice_realtime_eval_lane", None) or PRODUCTION_LANE).strip().upper()
    if raw in {"B", LANE_B, "NATIVE"}:
        return LANE_B
    if raw in {"C", LANE_C, "HYBRID"}:
        return LANE_C
    return LANE_A


def production_allows_lane(lane: str) -> bool:
    """Only the current cascade may serve live customer audio today."""
    return lane == LANE_A


def eval_card(*, lane: str) -> dict[str, Any]:
    return {
        "lane": lane,
        "production_default": lane == PRODUCTION_LANE,
        "production_allowed": production_allows_lane(lane),
        "tools_must_use_execute_task_streaming": True,
        "speculative_write": False,
        "benchmark_dimensions": list(BENCHMARK_DIMENSIONS),
    }

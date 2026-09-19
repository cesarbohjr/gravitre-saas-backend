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
    "webrtc_connection_startup",
    "webrtc_media_rtt",
    "webrtc_jitter",
    "webrtc_packet_loss",
    "webrtc_reconnect",
    "webrtc_region",
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


def production_voice_lane(_settings: Any | None = None) -> str:
    """Serving path is always cascade A. Eval env vars must not swap it."""
    return PRODUCTION_LANE


def shadow_eval_lane(settings: Any | None) -> str:
    """Named eval lane for comparison only — never a production transport/model swap."""
    return resolve_eval_lane(settings)


def eval_card(*, lane: str) -> dict[str, Any]:
    from app.services.voice_webrtc_eval import webrtc_eval_card

    return {
        "lane": lane,
        "production_default": lane == PRODUCTION_LANE,
        "production_allowed": production_allows_lane(lane),
        "tools_must_use_execute_task_streaming": True,
        "speculative_write": False,
        "benchmark_dimensions": list(BENCHMARK_DIMENSIONS),
        "webrtc": webrtc_eval_card(),
    }


def lane_comparison(*, measured: dict[str, Any] | None = None) -> dict[str, Any]:
    """A vs B vs C architecture table. Missing measurements stay NOT_RUN."""
    rows = {
        LANE_A: {
            "path": "Deepgram STT → execute_task_streaming → ElevenLabs",
            "production_allowed": True,
            "native_provider_tools": False,
            "tools": "execute_task_streaming only",
            "speculative_write": False,
            "media_transport": "websocket_pcm16_json",
        },
        LANE_B: {
            "path": "speech/audio model → execute_task_streaming for tools → audio",
            "production_allowed": False,
            "native_provider_tools": False,
            "tools": "execute_task_streaming only (provider-native tools forbidden)",
            "speculative_write": False,
            "media_transport": "eval",
            "risk": "ungoverned tools / lost HMAC trace if miswired",
        },
        LANE_C: {
            "path": "realtime conversation frontend + Gravitre work backend",
            "production_allowed": False,
            "native_provider_tools": False,
            "tools": "execute_task_streaming only",
            "speculative_write": False,
            "media_transport": "eval",
            "note": "preferred eval successor if B fails governance or traceability",
        },
    }
    scores = measured if isinstance(measured, dict) else {}
    for lane, row in rows.items():
        sample = scores.get(lane)
        row["measured"] = bool(isinstance(sample, dict) and sample)
        row["scores"] = sample if row["measured"] else "NOT_RUN"
        row["eval_card"] = eval_card(lane=lane)
    return {
        "production_voice_lane": PRODUCTION_LANE,
        "production_recommendation": PRODUCTION_LANE,
        "eval_hypothesis_if_b_fails_governance": LANE_C,
        "blended_voice_latency": None,
        "lanes": rows,
        "benchmark_dimensions": list(BENCHMARK_DIMENSIONS),
    }

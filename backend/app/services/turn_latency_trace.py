"""3.0-A full-turn latency critical-path analyzer.

Checkpoints are cumulative milliseconds from request start. The dominant stage is
the largest delta between successive marks — not the average of all turns.
Does not invent Metric A/B numbers. Does not weaken WRITE/HMAC.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

AUDIT_ACTION = "runtime.turn_latency.critical_path"

STAGE_CANONICAL = {
    "client_ready": "NETWORK",
    "workspace_focus_resolved": "NETWORK",
    "gateway": "RESOLUTION",
    "resolution": "RESOLUTION",
    "capability_route": "RESOLUTION",
    "connector_preflight": "PREFLIGHT",
    "context_entry": "CONTEXT_BUILD",
    "context_compile": "CONTEXT_BUILD",
    "context_inline": "CONTEXT_BUILD",
    "context_prefetch_adopted": "CONTEXT_BUILD",
    "assistant_turn_prepared": "CONTEXT_BUILD",
    "system_prompt_built": "CONTEXT_BUILD",
    "tool_discovery": "TOOL_DISCOVERY",
    "model_reasoning_started": "MODEL_TTFT",
    "react": "MODEL_TTFT",
    "execution": "PROVIDER",
    "compose": "COMPOSER",
    "terminal": "COMPOSER",
    "generation": "MODEL_TTFT",
}


def map_stage(name: str) -> str:
    key = str(name or "").strip()
    return STAGE_CANONICAL.get(key, key.upper() or "UNKNOWN")


def analyze_cumulative_checkpoints(marks: dict[str, int] | None) -> dict[str, Any]:
    """Return per-stage deltas and the dominant 3.0 stage name."""
    items = sorted(
        ((str(k), int(v)) for k, v in (marks or {}).items() if v is not None),
        key=lambda row: row[1],
    )
    stages: list[dict[str, Any]] = []
    prev_ms = 0
    for name, cumulative in items:
        delta = max(0, cumulative - prev_ms)
        stages.append(
            {
                "checkpoint": name,
                "stage": map_stage(name),
                "cumulative_ms": cumulative,
                "delta_ms": delta,
            }
        )
        prev_ms = cumulative
    dominant = max(stages, key=lambda row: int(row["delta_ms"])) if stages else None
    return {
        "stages": stages,
        "dominant_stage": str((dominant or {}).get("stage") or "UNKNOWN"),
        "dominant_checkpoint": str((dominant or {}).get("checkpoint") or ""),
        "dominant_ms": int((dominant or {}).get("delta_ms") or 0),
        "total_ms": prev_ms,
    }


def record_critical_path(
    settings: Any,
    *,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    turn_id: str | None,
    marks: dict[str, int] | None,
    spoken_mode: bool = False,
) -> dict[str, Any]:
    """Best-effort audit_events write. Never raises; never blocks the turn."""
    analysis = analyze_cumulative_checkpoints(marks)
    analysis["turn_id"] = turn_id
    analysis["spoken_mode"] = bool(spoken_mode)
    if not org_id or not user_id:
        logger.debug("turn_latency_critical_path_skipped reason=missing_org_or_user")
        return analysis
    try:
        from app.workflows.audit import write_audit_event
        from app.workflows.repository import get_supabase_client

        client = get_supabase_client(settings)
        write_audit_event(
            client,
            org_id,
            user_id,
            AUDIT_ACTION,
            "conversation",
            conversation_id or org_id,
            analysis,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("turn_latency_critical_path_write_failed error=%s", exc)
    return analysis

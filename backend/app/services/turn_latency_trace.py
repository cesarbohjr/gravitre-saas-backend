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
    "intent_gateway": "RESOLUTION",
    "resolution": "RESOLUTION",
    "capability_route": "RESOLUTION",
    "understanding": "UNDERSTANDING",
    "memory.recalled": "MEMORY",
    "compose_canned": "COMPOSER",
    "first_sse": "FIRST_SSE",
    "provider": "PROVIDER",
    "connector_preflight": "PREFLIGHT",
    "preflight": "PREFLIGHT",
    "context_entry": "CONTEXT_BUILD",
    "context_compile": "CONTEXT_BUILD",
    "context_inline": "CONTEXT_BUILD",
    "context_prefetch_adopted": "CONTEXT_BUILD",
    "assistant_turn_prepared": "CONTEXT_BUILD",
    "system_prompt_built": "CONTEXT_BUILD",
    "tool_discovery": "TOOL_DISCOVERY",
    "mcp_tools": "TOOL_DISCOVERY",
    "model_reasoning_started": "MODEL_TTFT",
    "react": "MODEL_TTFT",
    "react_entry": "MODEL_TTFT",
    "kernel_pre_act": "PLANNING",
    "execution": "PROVIDER",
    "compose": "COMPOSER",
    "terminal": "COMPOSER",
    "generation": "MODEL_TTFT",
    "vad": "VAD",
    "turn_detector": "STT_ENDPOINTING",
    "stt_partial": "STT",
    "stt_final": "STT",
    "tts_queue": "TTS_BUFFER",
    "tts_first_byte": "TTS_BUFFER",
    "first_audible_pcm": "TTS_BUFFER",
    "user_turn_finalization_ms": "STT_ENDPOINTING",
    "end_to_end_ms": "NETWORK",
    "llm_first_token_ms": "MODEL_TTFT",
    "tts_requested_ms": "TTS_BUFFER",
    "ttfa_ms": "TTS_BUFFER",
    "ttft_ms": "MODEL_TTFT",
}


def build_voice_http_turn_marks(
    *,
    completion_ms: int,
    first_text_ms: int | None = None,
    first_audio_ms: int | None = None,
    classify_done_ms: int | None = None,
    pre_act_done_ms: int | None = None,
    unified_breakdown: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Cumulative voice HTTP Talk marks from session wall clocks."""
    marks: dict[str, int] = {"client_ready": 0}
    if classify_done_ms is not None:
        marks["resolution"] = int(classify_done_ms)
    if pre_act_done_ms is not None:
        marks["preflight"] = int(pre_act_done_ms)
    if first_text_ms is not None:
        marks["llm_first_token_ms"] = int(first_text_ms)
    if first_audio_ms is not None:
        marks["tts_first_byte"] = int(first_audio_ms)
    if unified_breakdown:
        for key, raw in unified_breakdown.items():
            if isinstance(raw, (int, float)):
                val = int(raw)
                if val >= 0:
                    marks[str(key)] = val
    marks["terminal"] = int(completion_ms)
    return marks


def build_voice_pipecat_turn_marks(
    *,
    end_to_end_ms: int | None,
    user_turn_finalization_ms: int | None = None,
    llm_first_token_ms: int | None = None,
    llm_first_speakable_chunk_ms: int | None = None,
    tts_requested_ms: int | None = None,
    ttfb_by_processor_ms: dict[str, int] | None = None,
) -> dict[str, int]:
    """Cumulative Pipecat duplex marks from observer + LLM bridge timings."""
    marks: dict[str, int] = {"client_ready": 0}
    if user_turn_finalization_ms is not None:
        marks["user_turn_finalization_ms"] = int(user_turn_finalization_ms)
    if llm_first_token_ms is not None:
        marks["llm_first_token_ms"] = int(llm_first_token_ms)
    if llm_first_speakable_chunk_ms is not None:
        marks["generation"] = int(llm_first_speakable_chunk_ms)
    if tts_requested_ms is not None:
        marks["tts_requested_ms"] = int(tts_requested_ms)
    for proc, ms in (ttfb_by_processor_ms or {}).items():
        key = str(proc)
        if "CognitiveLLM" in key or key.endswith("LLMService"):
            marks.setdefault("llm_first_token_ms", int(ms))
        elif "TTS" in key or "ElevenLabs" in key:
            marks.setdefault("tts_first_byte", int(ms))
    if end_to_end_ms is not None:
        marks["end_to_end_ms"] = int(end_to_end_ms)
        marks["terminal"] = int(end_to_end_ms)
    return marks


def record_voice_turn_critical_path(
    settings: Any,
    *,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    turn_id: str | None,
    marks: dict[str, int] | None,
    transport: str,
) -> dict[str, Any]:
    """Voice-specific critical-path write (spoken_mode=True, transport label)."""
    payload_marks = dict(marks or {})
    analysis = analyze_cumulative_checkpoints(payload_marks)
    analysis["turn_id"] = turn_id
    analysis["spoken_mode"] = True
    analysis["voice_transport"] = str(transport or "")
    if not org_id or not user_id:
        logger.debug("voice_turn_critical_path_skipped reason=missing_org_or_user")
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
        logger.debug("voice_turn_critical_path_write_failed error=%s", exc)
    return analysis


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

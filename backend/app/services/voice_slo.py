"""Standing two-metric voice latency standard.

This is the permanent definition of "voice latency" for this program. A single
blended number (first-audio mixed with operator-task completion) misrepresents
both. Confirmed methodology: Full-Duplex-Bench-v3 and EVA-Bench; no published
production voice system, including Gemini Live 3.1 and GPT-Realtime, holds a
sub-500ms bar on genuine tool-calling / operator-shaped *completion*.

Metric A — Time to First Honest Response
    End of user speech → first genuine composed audio (loop-stage sourced
    when the Cognitive Loop is speaking; otherwise the composed answer).
    Hard target: P50 <500ms, P95 <800ms. Every turn. No exceptions.

Metric B — Operator-Task Completion Latency
    End of user speech → final composed answer on genuinely tool-using /
    multi-stage turns. Target: P50 <5s, P95 <8s (Gemini Live 3.1 measured
    ~4.25s P-equivalent on tool-calling turns).

STA-343 (option 1) is the speech mechanism for Metric A on operator turns.
Intent Gateway, Cognitive Loop Controller, and Response Composer are unchanged.
"""
from __future__ import annotations

from typing import Any

METRIC_A_ID = "time_to_first_honest_response"
METRIC_B_ID = "operator_task_completion_latency"
METRIC_A_P50_MS = 500
METRIC_A_P95_MS = 800
METRIC_B_P50_MS = 5000
METRIC_B_P95_MS = 8000

AUDIT_METRIC_A = "voice.slo.metric_a"
AUDIT_METRIC_B = "voice.slo.metric_b"

# Must stay identical to cognitive_loop_controller._SPOKEN_STAGE_DRAFTS["PERCEIVE"].
# Kept here so Metric A speech does not import the Cognitive Loop Controller on the
# first-audio critical path (that import was a measured 1s+ stall).
EARLY_PERCEIVE_DRAFT = (
    "I've classified this as a real request, so I'm running the full loop."
)

# Do not use these as a blended "voice latency" headline.
INTERNAL_DUPLEX_E2E_ACTION = "voice.turn_latency.e2e"

_WRITE_ACTION_HINTS = (
    ".create",
    ".update",
    ".delete",
    ".upsert",
    ".write",
    ".send",
    ".add",
    ".remove",
    ".publish",
    ".archive",
)


def _tool_name(row: Any) -> str:
    if isinstance(row, dict):
        fn = row.get("function") if isinstance(row.get("function"), dict) else {}
        return str(
            row.get("action")
            or row.get("invoke_action")
            or row.get("name")
            or row.get("tool")
            or fn.get("name")
            or ""
        ).strip()
    return str(getattr(row, "name", "") or getattr(row, "action", "") or "").strip()


def _tool_succeeded(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    if row.get("success") is True:
        return True
    out = row.get("output")
    if isinstance(out, dict) and out.get("success") is True:
        return True
    if row.get("error") or row.get("errorCode") or row.get("error_code"):
        return False
    return False


def _looks_mutating(action: str) -> bool:
    key = action.lower()
    return any(tok in key for tok in _WRITE_ACTION_HINTS)


def turn_claimed_write_complete(
    *,
    tool_results: list[Any] | None = None,
    execution_verified: bool = False,
    pending_task: dict[str, Any] | None = None,
) -> bool:
    """True only when a genuine mutating write already happened this turn.

    Plan staging (`awaiting_plan_confirm`) and reads are not writes. Classification
    intent alone is not enough — workflow_execution on a plan-without-execute
    turn must not block spoken delivery.
    """
    if execution_verified:
        return True
    status = str((pending_task or {}).get("status") or "").strip().lower()
    if status in {"awaiting_plan_confirm", "awaiting_params", "clarifying_question"}:
        # Approval hold: nothing has been claimed complete.
        for row in tool_results or []:
            name = _tool_name(row)
            if name and _looks_mutating(name) and _tool_succeeded(row):
                return True
        return False
    for row in tool_results or []:
        name = _tool_name(row)
        if name and _looks_mutating(name) and _tool_succeeded(row):
            return True
    return False


def verification_must_block_delivery(
    *,
    tool_results: list[Any] | None = None,
    execution_verified: bool = False,
    pending_task: dict[str, Any] | None = None,
    message: str = "",
    classification: dict[str, Any] | None = None,
) -> bool:
    """OBSERVE critic waits only for real writes or high-risk legal/financial reads.

    Plan staging and ordinary reads go async. ``workflow_execution`` intent on a
    plan-without-execute turn is not a completed write and must not block speech.
    """
    if turn_claimed_write_complete(
        tool_results=tool_results,
        execution_verified=execution_verified,
        pending_task=pending_task,
    ):
        return True
    status = str((pending_task or {}).get("status") or "").strip().lower()
    if status in {"awaiting_plan_confirm", "awaiting_params", "clarifying_question"}:
        return False
    from app.services.complexity_routing_guardrails import (
        _HIGH_RISK_FINANCIAL,
        _HIGH_RISK_LEGAL,
    )

    cls = classification if isinstance(classification, dict) else {}
    risk = str(cls.get("risk_level") or "").lower()
    if risk in {"high", "critical"}:
        return True
    text = str(message or "")
    return bool(_HIGH_RISK_LEGAL.search(text) or _HIGH_RISK_FINANCIAL.search(text))


def is_metric_a_source(first_text: str | None, *, loop_stage: str | None = None) -> str:
    """Label the first honest audio source for Metric A samples."""
    if loop_stage:
        return f"loop_stage:{str(loop_stage).upper()}"
    text = (first_text or "").strip()
    from app.services.cognitive_loop_controller import _SPOKEN_STAGE_DRAFTS

    for stage, draft in _SPOKEN_STAGE_DRAFTS.items():
        if draft and draft in text:
            return f"loop_stage:{stage}"
    return "composed_answer"


def operator_task_for_metric_b(
    *,
    operator_task: bool = False,
    loop_stage_spoken: bool = False,
    tool_results: list[Any] | None = None,
) -> bool:
    """Metric B is only for genuinely multi-stage / tool-using operator turns."""
    if operator_task or loop_stage_spoken:
        return True
    return bool(tool_results)

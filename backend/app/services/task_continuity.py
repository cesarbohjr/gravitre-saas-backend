"""2.0-H — one task frame for multi-turn continuity (CS-7).

ExecutionPlan remains SoT. pending_task / pending_action / offered_action /
active_analysis / compiled_task are projections of that frame, not competing
runtimes. Follow-ups update the same plan_id; explicit topic change restarts.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from app.services.execution_plan_service import ExecutionPlan
from app.services.reference_resolver import resolve_reference

ContinuityDecision = Literal["continue", "restart", "none"]

PENDING_FAMILY_KEYS = ("pending_task", "pending_action", "offered_action")

_CANCEL_RESTART = re.compile(
    r"(?is)^\s*(never\s+mind|nevermind|forget\s+(?:that|it)|start\s+over|"
    r"new\s+(?:task|question)|cancel(?:\s+that)?|different\s+(?:topic|question)|unrelated)\b"
)

_REFINE_RE = re.compile(
    r"(?is)\b("
    r"that|this|those|them|\bit\b|same(?:\s+(?:one|site|property|as\s+before))?|"
    r"break\s+(?:that|it)\s+down|for\s+that|use\s+that|compare\s+that|"
    r"instead|also\s+show|last\s+(?:week|month)|this\s+week|yesterday|"
    r"the\s+(?:first|second|third|last)\s+one|"
    r"only\s+the|large\s+ones|just\s+the|overdue|top\s+three|"
    r"who\s+owns|draft\s+a\s+summary|"
    r"draft\s+an\s+email|don'?t\s+send|"
    r"what\s+(?:appears\s+)?important|what\s+is\s+happening|"
    r"what\s+(?:is\s+)?missing|cannot\s+conclude|can(?:not|'t)\s+conclude|"
    r"what\s+should\s+i\s+(?:do|investigate|look)|(?:do|investigate)\s+next|"
    r"tell\s+me\s+more|go\s+deeper|why\s+(?:does|is)\s+that"
    r")\b"
)

_TOPIC_SWITCH = (
    ("analytics.traffic_overview", re.compile(r"\b(invoice|receivable|who owes|overdue|ticket|zendesk|pipeline|deals?)\b", re.I)),
    ("sales.pipeline.health", re.compile(r"\b(traffic|visitors?|ga4|invoice|receivable|ticket)\b", re.I)),
    ("finance.receivables.overdue", re.compile(r"\b(traffic|visitors?|ga4|pipeline|ticket|zendesk)\b", re.I)),
    ("support.issue_trends", re.compile(r"\b(traffic|visitors?|ga4|pipeline|invoice|receivable)\b", re.I)),
)


def pending_family(state: dict[str, Any] | None) -> dict[str, Any]:
    """Structured pending projections keyed by family name — not a second SoT."""
    raw = state if isinstance(state, dict) else {}
    out: dict[str, Any] = {}
    for key in PENDING_FAMILY_KEYS:
        value = raw.get(key)
        if isinstance(value, dict) and value:
            out[key] = value
    return out


def active_task_frame(task_state: dict[str, Any] | None) -> dict[str, Any] | None:
    """Single read model of the current task. Plan id wins over projections."""
    state = task_state if isinstance(task_state, dict) else {}
    plan = ExecutionPlan.from_dict(state.get("execution_plan"))
    compiled = state.get("compiled_task") if isinstance(state.get("compiled_task"), dict) else {}
    analysis = state.get("active_analysis") if isinstance(state.get("active_analysis"), dict) else {}
    if plan is None and not compiled and not analysis and not pending_family(state):
        return None
    inferred = None
    if not (plan.capability_id if plan else None) and not compiled.get("capability_id"):
        from app.services.operational_read_execution import infer_operational_recipe_id

        inferred = infer_operational_recipe_id(state)
    capability = (
        (plan.capability_id if plan else None)
        or compiled.get("capability_id")
        or inferred
        or analysis.get("kind")
        or state.get("capability_id")
        or None
    )
    return {
        "plan_id": (plan.plan_id if plan else None) or compiled.get("plan_id"),
        "capability_id": str(capability).strip() or None,
        "objective": (
            (plan.objective if plan else None)
            or compiled.get("objective_text")
            or analysis.get("kind")
            or ""
        ),
        "terminal_status": plan.terminal_status if plan else None,
        "plan": plan,
        "compiled_task": compiled or None,
        "active_analysis": analysis or None,
        "pending_family": pending_family(state),
    }


def _topic_switch(message: str, capability_id: str | None) -> bool:
    text = message or ""
    cap = str(capability_id or "")
    for prefix, pattern in _TOPIC_SWITCH:
        if cap == prefix or cap.startswith(prefix.split(".")[0] + "."):
            if pattern.search(text) and not _REFINE_RE.search(text):
                return True
    return False


def is_restart_utterance(message: str, task_state: dict[str, Any] | None = None) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if _CANCEL_RESTART.match(text):
        return True
    frame = active_task_frame(task_state)
    if frame and _topic_switch(text, frame.get("capability_id")):
        return True
    return False


def is_continuity_followup(message: str, task_state: dict[str, Any] | None) -> bool:
    """True when this turn should keep the same plan_id / compiled_task frame."""
    if is_restart_utterance(message, task_state):
        return False
    frame = active_task_frame(task_state)
    if frame is None:
        return False
    reference = resolve_reference(message, task_state)
    if reference.matched:
        return True
    text = (message or "").strip()
    if not text:
        return False
    if _REFINE_RE.search(text):
        return True
    return False


def decide_task_continuity(message: str, task_state: dict[str, Any] | None) -> ContinuityDecision:
    frame = active_task_frame(task_state)
    if frame is None:
        return "none"
    if is_restart_utterance(message, task_state):
        return "restart"
    if is_continuity_followup(message, task_state):
        return "continue"
    status = str(frame.get("terminal_status") or "")
    if status in {"pending", "running", "waiting_for_approval"}:
        return "continue"
    return "none"


def frame_is_analytics(task_state: dict[str, Any] | None) -> bool:
    frame = active_task_frame(task_state)
    cap = str((frame or {}).get("capability_id") or "")
    analysis = (frame or {}).get("active_analysis") if frame else None
    if cap.startswith("analytics."):
        return True
    if isinstance(analysis, dict) and str(analysis.get("kind") or "").startswith("analytics."):
        return True
    compiled = (frame or {}).get("compiled_task") if frame else None
    if isinstance(compiled, dict):
        keys = compiled.get("action_keys") or []
        if any("google_analytics" in str(k) or "analytics" in str(k) for k in keys):
            return True
    return False

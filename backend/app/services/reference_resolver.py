"""Structured reference resolution for conversational shorthand."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

ReferenceKind = Literal[
    "confirm",
    "reject",
    "select_all_options",
    "select_option",
    "referent",
    "same_as_before",
    "none",
]


@dataclass(frozen=True)
class ReferenceResolution:
    kind: ReferenceKind
    matched: bool = False
    reason: str = ""
    selected_option_ids: tuple[str, ...] = field(default_factory=tuple)
    selected_indices: tuple[int, ...] = field(default_factory=tuple)
    referent: dict[str, Any] | None = None
    pending_target: str | None = None


_CONFIRM_RE = re.compile(
    r"^\s*(yes|yeah|yep|y|confirm|confirmed|go ahead|proceed|do it|"
    r"sounds good|approved|sure|ok|okay|please do|let's do it|lets do it)\s*[.!]?\s*$",
    re.I,
)

_ALL_OPTIONS_RE = re.compile(
    r"(?is)^\s*(?:"
    r"all\s+\d+|all\s+three|all\s+of\s+(?:them|those|it)|everything|yes\s+all|both"
    r")\s*[.!]?\s*$",
)

_ORDINAL_RE = re.compile(
    r"(?is)^\s*(?:the\s+)?(first|second|third|last|1st|2nd|3rd|\d+(?:st|nd|rd|th)?)\s*(?:one|option)?\s*[.!]?\s*$",
)

_THOSE_RE = re.compile(r"(?is)\b(those|these|them|it|that|same one|same as before)\b")

_COMPARE_THAT_RE = re.compile(
    r"(?is)\bcompare\s+(?:that|it|this)\s+(?:to|with|against)\s+",
)


def _option_set(state: dict[str, Any]) -> list[dict[str, Any]]:
    raw = state.get("previous_option_set")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    offered = state.get("offered_action")
    if isinstance(offered, dict):
        options = offered.get("options")
        if isinstance(options, list):
            return [item for item in options if isinstance(item, dict)]
    session = state.get("connector_session") if isinstance(state.get("connector_session"), dict) else {}
    pending_options = session.get("pendingOptions")
    if isinstance(pending_options, list):
        return [item for item in pending_options if isinstance(item, dict)]
    return []


def _active_analysis(state: dict[str, Any]) -> dict[str, Any] | None:
    active = state.get("active_analysis")
    if isinstance(active, dict):
        return active
    session = state.get("connector_session") if isinstance(state.get("connector_session"), dict) else {}
    entities = session.get("activeEntities") if isinstance(session.get("activeEntities"), dict) else {}
    overview = entities.get("analytics_traffic_overview")
    if isinstance(overview, dict):
        return {
            "kind": "analytics.traffic_overview",
            "connector_id": overview.get("connectorId"),
            "property_id": overview.get("propertyId"),
            "property_name": overview.get("propertyName"),
        }
    previous = state.get("previous_result")
    if isinstance(previous, dict):
        return previous
    return None


def _pending_confirmation_target(state: dict[str, Any]) -> str | None:
    offered = state.get("offered_action")
    if isinstance(offered, dict) and offered.get("status") in {
        "awaiting_user_confirmation",
        "awaiting_confirm",
    }:
        return "offered_action"
    pending = state.get("pending_task")
    if isinstance(pending, dict) and pending.get("status") in {
        "awaiting_confirm",
        "awaiting_plan_confirm",
        "awaiting_step_confirm",
        "awaiting_admin_approval",
    }:
        return "pending_task"
    if isinstance(offered, dict) and offered.get("confirmation_required"):
        return "offered_action"
    pending_action = state.get("pending_action")
    if isinstance(pending_action, dict) and pending_action.get("status") in {
        "awaiting_user",
        "awaiting_user_confirmation",
        "awaiting_confirm",
    }:
        return "pending_action"
    return None


def _ordinal_index(text: str) -> int | None:
    match = _ORDINAL_RE.match(text.strip())
    if not match:
        return None
    token = match.group(1).lower()
    mapping = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "last": -1}
    if token in mapping:
        return mapping[token]
    digits = re.match(r"(\d+)", token)
    if digits:
        return max(int(digits.group(1)) - 1, 0)
    return None


def _task_frame_referent(state: dict[str, Any]) -> dict[str, Any] | None:
    analysis = _active_analysis(state)
    if analysis:
        return analysis
    compiled = state.get("compiled_task") if isinstance(state.get("compiled_task"), dict) else {}
    if compiled.get("capability_id") or compiled.get("sources") or compiled.get("plan_id"):
        return {
            "kind": compiled.get("capability_id") or "task",
            "plan_id": compiled.get("plan_id"),
            "objective_text": compiled.get("objective_text"),
            "sources": compiled.get("sources"),
        }
    plan = state.get("execution_plan") if isinstance(state.get("execution_plan"), dict) else {}
    if plan.get("plan_id"):
        return {
            "kind": plan.get("capability_id") or "task",
            "plan_id": plan.get("plan_id"),
            "objective_text": plan.get("objective") or plan.get("summary"),
        }
    return None


def resolve_reference(message: str, task_state: dict[str, Any] | None) -> ReferenceResolution:
    """Resolve confirmations, option shorthand, and referents against structured state."""
    text = (message or "").strip()
    state = task_state if isinstance(task_state, dict) else {}
    if not text:
        return ReferenceResolution(kind="none", matched=False, reason="empty_message")

    pending_target = _pending_confirmation_target(state)
    if _CONFIRM_RE.match(text):
        if pending_target:
            return ReferenceResolution(
                kind="confirm",
                matched=True,
                reason=f"confirm_{pending_target}",
                pending_target=pending_target,
            )
        return ReferenceResolution(kind="confirm", matched=False, reason="no_pending_confirmation")

    from app.services.conversational_execution_service import DECLINE_PATTERN

    if DECLINE_PATTERN.match(text):
        if pending_target:
            return ReferenceResolution(kind="reject", matched=True, reason=f"reject_{pending_target}")
        return ReferenceResolution(kind="reject", matched=False, reason="no_pending_rejection")

    options = _option_set(state)
    if _ALL_OPTIONS_RE.match(text) and options:
        ids = tuple(str(item.get("id") or item.get("label") or idx) for idx, item in enumerate(options))
        indices = tuple(range(len(options)))
        return ReferenceResolution(
            kind="select_all_options",
            matched=True,
            reason="all_options_shorthand",
            selected_option_ids=ids,
            selected_indices=indices,
        )

    ordinal = _ordinal_index(text)
    if ordinal is not None and options:
        if ordinal < 0:
            ordinal = len(options) + ordinal
        if 0 <= ordinal < len(options):
            item = options[ordinal]
            return ReferenceResolution(
                kind="select_option",
                matched=True,
                reason="ordinal_option",
                selected_option_ids=(str(item.get("id") or item.get("label") or ordinal),),
                selected_indices=(ordinal,),
            )

    if _COMPARE_THAT_RE.search(text) or (text.lower().strip() in {"that", "it", "same one", "same as before"}):
        referent = _task_frame_referent(state)
        if referent:
            return ReferenceResolution(
                kind="referent",
                matched=True,
                reason="active_analysis",
                referent=referent,
            )

    if _THOSE_RE.search(text):
        referent = _task_frame_referent(state)
        if referent:
            return ReferenceResolution(
                kind="referent",
                matched=True,
                reason="demonstrative_pronoun",
                referent=referent,
            )

    return ReferenceResolution(kind="none", matched=False, reason="no_reference_match")


def store_option_set(task_state: dict[str, Any], options: list[dict[str, Any]]) -> dict[str, Any]:
    """Persist structured options for later all-N / ordinal resolution."""
    return {
        **task_state,
        "previous_option_set": options,
        "connector_session": {
            **(task_state.get("connector_session") if isinstance(task_state.get("connector_session"), dict) else {}),
            "pendingOptions": options,
        },
    }


def store_active_analysis(task_state: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        **task_state,
        "active_analysis": analysis,
        "previous_result": analysis,
    }

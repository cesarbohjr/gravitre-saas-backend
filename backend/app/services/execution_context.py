"""Canonical execution context assembled from durable conversation state.

This is a projection, not a second memory system. Text, voice, approvals and
replanning can consume the same normalized task context without copying state
into modality-specific stores.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def _dict(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _list(value: Any, *, limit: int = 20) -> list[Any]:
    return deepcopy(value[-limit:]) if isinstance(value, list) else []


def build_execution_context(
    *,
    task_state: dict[str, Any] | None,
    conversation_history: list[Any] | None = None,
    surface: str = "ai_chat",
    entry_point: str = "unknown",
    originating_modality: str = "text",
) -> dict[str, Any]:
    """Return the one normalized context contract used before planning.

    The projection intentionally contains only durable/observable state. It does
    not expose hidden reasoning and does not infer a new user request from an old
    execution, which keeps intentional repeats ("send another one") distinct.
    """
    state = task_state if isinstance(task_state, dict) else {}
    connector = _dict(state.get("connector_session"))
    active_entities = _dict(connector.get("activeEntities"))
    if not active_entities:
        active_entities = _dict(state.get("resolved_entities"))

    prior_actions = _list(state.get("recent_connector_invocations"), limit=8)
    observations = _list(state.get("execution_observations"), limit=20)
    artifacts = _list(state.get("work_artifacts"), limit=20)
    recent_user_messages = _list(state.get("recent_user_messages"), limit=12)

    history_tail: list[dict[str, str]] = []
    for row in list(conversation_history or [])[-12:]:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "").strip().lower()
        content = str(row.get("content") or row.get("message") or "").strip()
        if role in {"user", "assistant"} and content:
            history_tail.append({"role": role, "content": content[:1200]})

    return {
        "version": 1,
        "surface": str(surface or "ai_chat"),
        "entry_point": str(entry_point or "unknown"),
        "originating_modality": str(originating_modality or "text"),
        "active_entities": active_entities,
        "resolved_entities": _dict(state.get("resolved_entities")),
        "referenced_artifacts": artifacts,
        "current_plan": _dict(state.get("execution_plan") or state.get("current_plan")),
        "prior_observations": observations,
        "prior_verified_actions": [
            row for row in prior_actions
            if isinstance(row, dict)
            and str(row.get("verification_status") or row.get("status") or "").lower()
            in {"verified", "completed"}
        ],
        "recent_connector_invocations": prior_actions,
        "pending_action": _dict(state.get("pending_action") or state.get("pending_task")),
        "durable_checkpoint": _dict(state.get("durable_checkpoint")),
        "provider_result_evidence": _dict(state.get("provider_result_evidence")),
        "parameter_ledger": _dict(state.get("parameter_ledger")),
        "recent_user_messages": recent_user_messages,
        "conversation_tail": history_tail,
        "unresolved_dependencies": _list(state.get("pending_steps"), limit=20),
    }

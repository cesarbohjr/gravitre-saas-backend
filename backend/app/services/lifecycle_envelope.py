"""Unified lifecycle envelope for chat, voice, UI, and ROI surfaces.

Maps the internal semantic stage (``action_lifecycle``) to a stable customer-facing
envelope without adding a second state store.
"""
from __future__ import annotations

from typing import Any

from app.services.action_lifecycle import (
    composer_envelope_from_turn,
    logical_action_id,
    provider_record_id,
    semantic_stage_from_state,
)

CUSTOMER_STAGE: dict[str, str] = {
    "PREPARED": "accepted",
    "AWAITING_APPROVAL": "accepted",
    "APPROVED": "accepted",
    "EXECUTING": "verifying",
    "VERIFYING": "verifying",
    "EXECUTED_UNVERIFIED": "verifying",
    "VERIFIED": "verified",
    "COMPLETED": "verified",
    "FAILED": "failed",
    "REJECTED": "cancelled",
    "CANCELLED": "cancelled",
    "OUTCOME_UNCERTAIN": "uncertain",
    "AWAITING_RECONCILIATION": "uncertain",
}

LIFECYCLE_TOUCH_KEYS = frozenset(
    {
        "pending_task",
        "pending_action",
        "execution_plan",
        "execution_observations",
        "action_lifecycle",
        "connector_session",
    }
)


def build_lifecycle_envelope(
    task_state: dict[str, Any] | None,
    *,
    execution: Any | None = None,
    org_id: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    state = task_state if isinstance(task_state, dict) else {}
    stage = semantic_stage_from_state(state)
    compose = composer_envelope_from_turn(task_state=state, execution=execution)
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
    invoke = str(params.get("invoke_action") or pending.get("invoke_action") or "").strip()
    structured = {}
    obs = state.get("execution_observations")
    if isinstance(obs, list) and obs and isinstance(obs[-1], dict):
        structured = obs[-1].get("structured") if isinstance(obs[-1].get("structured"), dict) else {}
    logical_id = None
    if invoke and org_id and conversation_id:
        logical_id = logical_action_id(
            org_id=org_id,
            conversation_id=conversation_id,
            invoke_action=invoke,
            pending_action_id=str(pending.get("id") or ""),
            args=params.get("args") if isinstance(params.get("args"), dict) else {},
        )
    record_id = provider_record_id(structured) or params.get("provider_record_id")
    customer = CUSTOMER_STAGE.get(stage, "accepted")
    return {
        "semantic_stage": stage,
        "customer_stage": customer,
        "execution_verified": bool(compose.get("execution_verified")),
        "provider_result_evidence": bool(compose.get("provider_result_evidence")),
        "uncertain": bool(compose.get("data", {}).get("uncertain")),
        "logical_action_id": logical_id,
        "provider_record_id": str(record_id) if record_id else None,
        "pending_invoke_action": invoke or None,
    }


def enrich_task_state_with_lifecycle_envelope(
    task_state: dict[str, Any],
    *,
    org_id: str | None = None,
    conversation_id: str | None = None,
    execution: Any | None = None,
) -> dict[str, Any]:
    envelope = build_lifecycle_envelope(
        task_state,
        execution=execution,
        org_id=org_id,
        conversation_id=conversation_id,
    )
    task_state["lifecycle_envelope"] = envelope
    task_state["action_lifecycle"] = envelope["semantic_stage"]
    return task_state


def patch_needs_lifecycle_refresh(patch: dict[str, Any]) -> bool:
    return bool(LIFECYCLE_TOUCH_KEYS.intersection(patch.keys()))

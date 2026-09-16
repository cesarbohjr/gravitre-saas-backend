"""Phase E5.7 — Voice/text ExecutionPlan semantic equivalence checks."""
from __future__ import annotations

from typing import Any

from app.services.execution_plan_service import ExecutionPlan, reconcile_execution_plan


def reconcile_for_modality(
    message: str,
    *,
    task_state: dict[str, Any] | None = None,
    spoken_mode: bool = False,
    connected_integrations: list[str] | None = None,
) -> ExecutionPlan:
    """Voice shares task_state; spoken_mode is modality metadata only."""
    state = dict(task_state or {})
    if spoken_mode:
        state["voice_modality"] = {"spoken_mode": True}
    return reconcile_execution_plan(
        message=message,
        task_state=state,
        connected_integrations=connected_integrations,
    )


def plans_semantically_equivalent(a: ExecutionPlan, b: ExecutionPlan) -> bool:
    """Compare objective, steps, strategy — not byte-identical serialization."""
    if (a.objective or a.summary).strip().lower() != (b.objective or b.summary).strip().lower():
        return False
    if len(a.steps) != len(b.steps):
        return False
    for sa, sb in zip(a.steps, b.steps, strict=True):
        if sa.kind != sb.kind:
            return False
        if (sa.action_key or sa.title) != (sb.action_key or sb.title):
            return False
        if sa.connector_id != sb.connector_id:
            return False
    return (a.execution_strategy or "") == (b.execution_strategy or "")

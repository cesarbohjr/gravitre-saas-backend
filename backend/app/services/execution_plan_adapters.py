"""Phase E5 — compatibility adapters projecting legacy plan producers into ExecutionPlan."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep, StepKind
from app.services.pending_action_service import (
    PendingAction,
    pending_action_from_offered,
    pending_action_from_pending_task,
    pending_action_patch,
)


def _step_kind_from_connector(plan: ConnectorActionPlan) -> StepKind:
    kind = str(plan.kind or "").strip().lower()
    if kind in {"read", "query", "retrieve"}:
        return "read"
    if kind in {"clarify", "clarification"}:
        return "clarify"
    if kind in {"compose", "synthesis"}:
        return "compose"
    return "write"


def execution_plan_from_connector_action(
    plan: ConnectorActionPlan,
    *,
    plan_id: str | None = None,
    source: str = "connector_action",
    objective: str | None = None,
) -> ExecutionPlan:
    step_kind = _step_kind_from_connector(plan)
    return ExecutionPlan(
        plan_id=plan_id or str(uuid4()),
        summary=objective or plan.label or plan.invoke_action,
        objective=objective or plan.label or plan.invoke_action,
        steps=[
            ExecutionStep(
                step_id="connector_primary",
                title=plan.label or plan.invoke_action,
                kind=step_kind,
                connector_id=plan.integration,
                action_key=plan.invoke_action,
                status="pending",
                meta={
                    "tool_name": plan.tool_name,
                    "requires_approval": plan.requires_approval,
                    "destructive": plan.destructive,
                    "args": dict(plan.args),
                },
            )
        ],
        source=source,
        terminal_status="waiting_for_approval" if plan.requires_approval else "pending",
    )


def execution_plan_from_orchestration_steps(
    steps: list[Any],
    *,
    plan_id: str | None = None,
    summary: str = "Orchestrated multi-step plan",
    source: str = "orchestration",
) -> ExecutionPlan:
    exec_steps: list[ExecutionStep] = []
    for idx, row in enumerate(steps):
        plan_obj = getattr(row, "plan", None)
        if plan_obj is not None and isinstance(plan_obj, ConnectorActionPlan):
            kind = _step_kind_from_connector(plan_obj)
            exec_steps.append(
                ExecutionStep(
                    step_id=str(getattr(row, "step_id", None) or f"orch_{idx}"),
                    title=str(getattr(row, "label", None) or plan_obj.label or f"Step {idx + 1}"),
                    kind=kind,
                    connector_id=plan_obj.integration,
                    action_key=plan_obj.invoke_action,
                    status="pending",
                    meta={
                        "orchestration_kind": getattr(row, "kind", None),
                        "requires_approval": bool(getattr(row, "requires_approval", False)),
                        "supported": bool(getattr(row, "supported", True)),
                    },
                )
            )
            continue
        exec_steps.append(
            ExecutionStep(
                step_id=str(getattr(row, "step_id", None) or f"orch_{idx}"),
                title=str(getattr(row, "label", None) or f"Step {idx + 1}"),
                kind="read" if str(getattr(row, "kind", "")).lower() == "read" else "write",
                status="pending",
                meta={"legacy_orchestration": True},
            )
        )
    return ExecutionPlan(
        plan_id=plan_id or str(uuid4()),
        summary=summary,
        objective=summary,
        steps=exec_steps,
        source=source,
        execution_strategy="SEQUENTIAL",
    )


def execution_plan_from_offered_action(
    offered: dict[str, Any],
    *,
    plan_id: str | None = None,
    objective: str = "Business health inspection",
) -> ExecutionPlan:
    tools = [str(t) for t in (offered.get("tools") or []) if str(t).strip()]
    scope = [str(s) for s in (offered.get("scope") or []) if str(s).strip()]
    steps: list[ExecutionStep] = []
    parallel_group = "offered_read_tools"
    for idx, tool in enumerate(tools):
        steps.append(
            ExecutionStep(
                step_id=f"offered_read_{idx}_{tool}",
                title=f"Read {tool.replace('_', ' ')}",
                kind="read",
                action_key=tool,
                status="pending",
                meta={
                    "parallel_group": parallel_group,
                    "scope": scope,
                    "offered_tool": tool,
                },
            )
        )
    if steps:
        steps.append(
            ExecutionStep(
                step_id="offered_compose",
                title="Synthesize health findings",
                kind="compose",
                status="pending",
                meta={"depends_on_parallel_group": parallel_group},
            )
        )
    status = str(offered.get("status") or "")
    terminal = "pending"
    if status == "completed":
        terminal = "completed"
    elif status == "failed":
        terminal = "failed"
    elif status in {"awaiting_user_confirmation", "awaiting_confirm"}:
        terminal = "pending"

    return ExecutionPlan(
        plan_id=plan_id or str(uuid4()),
        summary=objective,
        objective=objective,
        steps=steps,
        source="offered_action",
        execution_strategy="PARALLEL" if len(tools) > 1 else "DIRECT",
        terminal_status=terminal,  # type: ignore[arg-type]
        pending_action_id=offered.get("pending_action_id"),
    )


def project_pending_task_from_plan(
    plan: ExecutionPlan,
    *,
    legacy_pending: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compatibility projection: pending_task reflects plan, does not own execution truth."""
    pending = dict(legacy_pending or {})
    primary = plan.steps[0] if plan.steps else None
    pending.setdefault("type", "execution_plan_projection")
    pending["execution_plan_id"] = plan.plan_id
    pending["status"] = pending.get("status") or "awaiting_confirm"
    if primary is not None:
        pending.setdefault("action", primary.action_key or primary.title)
        pending.setdefault("connector_id", primary.connector_id)
        pending.setdefault("params", dict(primary.meta.get("args") or {}))
    pending["_projection"] = True
    pending["_projection_source"] = "execution_plan"
    return pending


def bridge_offered_action_with_plan(
    offered: dict[str, Any],
    *,
    existing_plan: ExecutionPlan | None = None,
) -> tuple[ExecutionPlan, PendingAction, dict[str, Any]]:
    """Create or reuse ExecutionPlan + PendingAction for an offered READ continuation."""
    plan_id = str(
        offered.get("execution_plan_id")
        or (existing_plan.plan_id if existing_plan else "")
        or uuid4()
    )
    plan = existing_plan or execution_plan_from_offered_action(offered, plan_id=plan_id)

    pending_action = pending_action_from_offered(
        offered_id=str(offered.get("id") or uuid4()),
        plan_id=plan.plan_id,
        scope=offered.get("scope") if isinstance(offered.get("scope"), list) else [],
        tools=offered.get("tools") if isinstance(offered.get("tools"), list) else [],
    )
    pending_action.revision = plan.revision
    plan.pending_action_id = pending_action.pending_action_id

    bridged_offered = {
        **offered,
        "execution_plan_id": plan.plan_id,
        "pending_action_id": pending_action.pending_action_id,
    }
    return plan, pending_action, bridged_offered


def bridge_pending_task_with_plan(
    pending: dict[str, Any],
    *,
    existing_plan: ExecutionPlan | None = None,
    objective: str | None = None,
) -> tuple[ExecutionPlan, PendingAction, dict[str, Any]]:
    """Project legacy pending_task into canonical ExecutionPlan + PendingAction."""
    plan_id = str(
        pending.get("execution_plan_id")
        or (existing_plan.plan_id if existing_plan else "")
        or uuid4()
    )
    if existing_plan is not None:
        plan = existing_plan
    else:
        action = str(pending.get("action") or pending.get("tool") or "pending_action")
        plan = ExecutionPlan(
            plan_id=plan_id,
            summary=objective or action,
            objective=objective or action,
            steps=[
                ExecutionStep(
                    step_id="pending_primary",
                    title=action,
                    kind="write" if pending.get("requires_approval") else "read",
                    connector_id=str(pending.get("connector_id") or "") or None,
                    action_key=action,
                    status="pending",
                    meta={"pending_status": pending.get("status"), "args": dict(pending.get("params") or {})},
                )
            ],
            source="pending_task_bridge",
            terminal_status="waiting_for_approval"
            if pending.get("requires_approval") or pending.get("status") == "awaiting_confirm"
            else "pending",
        )
    pending_action = pending_action_from_pending_task(pending, plan_id=plan.plan_id)
    pending_action.revision = plan.revision
    plan.pending_action_id = pending_action.pending_action_id
    projected = project_pending_task_from_plan(plan, legacy_pending=pending)
    projected["pending_action_id"] = pending_action.pending_action_id
    return plan, pending_action, projected


def enrich_task_state_patch(
    updates: dict[str, Any],
    *,
    current_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Transitional ingress + authoritative egress for ExecutionPlan.

    Ingress (legacy → canonical): only when no canonical plan exists yet.
    Egress (canonical → projection): when ExecutionPlan is authoritative,
    pending_task is projected from plan — never the reverse.
    """
    from app.services.execution_plan_authority import (
        authoritative_execution_plan,
        is_legacy_ingress_only,
        pending_task_is_projection,
    )

    patch = dict(updates)
    state = current_state if isinstance(current_state, dict) else {}

    canonical = authoritative_execution_plan(state)
    incoming_plan = ExecutionPlan.from_dict(patch.get("execution_plan"))
    if incoming_plan is not None:
        canonical = incoming_plan

    if canonical is not None:
        if isinstance(patch.get("pending_task"), dict):
            patch["pending_task"] = project_pending_task_from_plan(
                canonical,
                legacy_pending=patch["pending_task"],
            )
        pending_action = state.get("pending_action")
        if isinstance(pending_action, dict) and pending_action.get("plan_id") != canonical.plan_id:
            patch.setdefault(
                "pending_action",
                {
                    **pending_action,
                    "plan_id": canonical.plan_id,
                    "revision": canonical.revision,
                },
            )
        return patch

    offered = patch.get("offered_action")
    if offered is None and "offered_action" not in patch:
        offered = state.get("offered_action")
    if isinstance(offered, dict) and offered.get("status") in {
        "awaiting_user_confirmation",
        "awaiting_confirm",
    }:
        if not offered.get("execution_plan_id"):
            plan, pending_action, bridged = bridge_offered_action_with_plan(offered)
            patch.update(execution_plan_bundle_patch(plan, pending_action, offered=bridged))
            return patch

    pending = patch.get("pending_task")
    if is_legacy_ingress_only(pending, canonical=None) and not pending_task_is_projection(pending):
        plan, pending_action, projected = bridge_pending_task_with_plan(pending)  # type: ignore[arg-type]
        patch.update(
            execution_plan_bundle_patch(
                plan,
                pending_action,
                pending_task=projected,
            )
        )
    return patch


def execution_plan_bundle_patch(
    plan: ExecutionPlan,
    pending_action: PendingAction | None = None,
    *,
    offered: dict[str, Any] | None = None,
    pending_task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from app.services.execution_plan_service import execution_plan_patch

    patch: dict[str, Any] = {**execution_plan_patch(plan)}
    if pending_action is not None:
        patch.update(pending_action_patch(pending_action))
    if offered is not None:
        patch["offered_action"] = offered
    if pending_task is not None:
        patch["pending_task"] = pending_task
    return patch

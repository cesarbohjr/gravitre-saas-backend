"""Policy-gated operator auto-execute (STA-106)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from app.workflows.audit import write_audit_event

ExecutionMode = Literal["plan_only", "auto_with_approval", "auto_trusted_scopes"]

_PLAN_ONLY_PROMPT = (
    "You are the Gravitre AI Operator, an enterprise automation planner. "
    "Convert the task into a safe, concrete plan proposal that touches only the "
    "user's connected systems. Never auto-execute; plans require human approval. "
    "If the task is empty, ambiguous, or out of scope, state what is missing in "
    "analysis_summary and use a low confidence value."
)

_AUTO_PROMPT = (
    "You are the Gravitre AI Operator, an enterprise automation planner. "
    "Convert the task into a safe, concrete plan that may be executed automatically "
    "when org policy and trusted scopes allow. Prefer read-only inspection steps first. "
    "Flag requires_approval=true for destructive or external-facing actions. "
    "If the task is empty, ambiguous, or out of scope, state what is missing in "
    "analysis_summary and use a low confidence value."
)

AUDIT_AUTO_EXECUTE_ENABLED = "operator.auto_execute.enabled"
AUDIT_AUTO_EXECUTE_ATTEMPT = "operator.auto_execute.attempted"


def get_execution_mode(operator: dict[str, Any]) -> ExecutionMode:
    mode = str(operator.get("execution_mode") or "plan_only").strip()
    if mode in {"plan_only", "auto_with_approval", "auto_trusted_scopes"}:
        return mode  # type: ignore[return-value]
    return "plan_only"


def get_operator_system_prompt(operator: dict[str, Any]) -> str:
    if get_execution_mode(operator) == "plan_only":
        return _PLAN_ONLY_PROMPT
    return _AUTO_PROMPT


def get_trusted_scopes(operator: dict[str, Any]) -> set[str]:
    raw = operator.get("auto_execute_trusted_scopes") or []
    if not isinstance(raw, list):
        return set()
    return {str(item).strip() for item in raw if str(item).strip()}


def step_matches_trusted_scopes(operator: dict[str, Any], step: dict[str, Any]) -> bool:
    trusted = get_trusted_scopes(operator)
    if not trusted:
        trusted = {"member", "execute_workflow"}
    explanation = step.get("explanation") or {}
    step_type = str(step.get("step_type") or "")
    permissions = {str(p) for p in (explanation.get("permissions_required") or [])}
    if step_type in trusted:
        return True
    if permissions and permissions.issubset(trusted):
        return True
    return False


def step_is_auto_eligible(operator: dict[str, Any], step: dict[str, Any]) -> bool:
    mode = get_execution_mode(operator)
    if mode == "plan_only":
        return False
    explanation = step.get("explanation") or {}
    if not explanation.get("executable") or explanation.get("draft_only"):
        return False
    if explanation.get("admin_required"):
        return False
    approval_required = bool(explanation.get("approval_required"))
    if approval_required and mode == "auto_trusted_scopes":
        return False
    if mode == "auto_with_approval":
        return True
    return step_matches_trusted_scopes(operator, step)


def apply_auto_execute_guardrails(plan: dict[str, Any], operator: dict[str, Any]) -> dict[str, Any]:
    mode = get_execution_mode(operator)
    guardrails = plan.get("guardrails") or {}
    exec_restrictions = list(guardrails.get("execution_restrictions") or [])
    no_auto = "No auto-execution. Confirmation required for any action."

    for step in plan.get("steps") or []:
        explanation = step.get("explanation") or {}
        if mode != "plan_only" and step_is_auto_eligible(operator, step):
            explanation["confirmation_required"] = False
        elif explanation.get("executable"):
            explanation["confirmation_required"] = True
        step["explanation"] = explanation

    if mode != "plan_only":
        exec_restrictions = [r for r in exec_restrictions if r != no_auto]
        exec_restrictions.append(
            f"Auto-execute mode: {mode}. Trusted scopes: {sorted(get_trusted_scopes(operator)) or ['default']}"
        )
    elif no_auto not in exec_restrictions:
        exec_restrictions.append(no_auto)

    guardrails["execution_restrictions"] = exec_restrictions
    plan["guardrails"] = guardrails
    return plan


def update_operator_auto_execute(
    client: Any,
    *,
    org_id: str,
    operator_id: str,
    execution_mode: ExecutionMode,
    trusted_scopes: list[str] | None,
    actor_id: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "execution_mode": execution_mode,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if trusted_scopes is not None:
        payload["auto_execute_trusted_scopes"] = trusted_scopes
    if execution_mode == "plan_only":
        payload["auto_execute_enabled_at"] = None
        payload["auto_execute_enabled_by"] = None
    else:
        payload["auto_execute_enabled_at"] = datetime.now(timezone.utc).isoformat()
        payload["auto_execute_enabled_by"] = actor_id

    updated = (
        client.table("operators")
        .update(payload)
        .eq("org_id", org_id)
        .eq("id", operator_id)
        .execute()
    )
    if not updated.data:
        raise ValueError("Operator not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_AUTO_EXECUTE_ENABLED,
        resource_type="operator",
        resource_id=operator_id,
        metadata={
            "executionMode": execution_mode,
            "trustedScopes": trusted_scopes or get_trusted_scopes(updated.data[0]),
        },
    )
    return dict(updated.data[0])


def find_auto_executable_step(operator: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    for step in steps:
        if step_is_auto_eligible(operator, step):
            return step
    return None


async def try_auto_execute_plan_step(
    *,
    client: Any,
    settings: Any,
    org_id: str,
    environment: str,
    operator: dict[str, Any],
    stored_plan: dict[str, Any],
    session: dict[str, Any],
    current_user: dict[str, Any],
) -> dict[str, Any] | None:
    """Auto-run or queue the first eligible plan step when policy allows."""
    from app.operators.repository import (
        create_operator_action,
        update_action_plan_status,
        update_operator_session_status,
    )
    from app.operators.services.execution import execute_operator_workflow, resolve_execution_target
    from app.workflows.policy import get_user_role

    step = find_auto_executable_step(operator, list(stored_plan.get("steps") or []))
    if not step:
        return None

    explanation = step.get("explanation") or {}
    plan_id = str(stored_plan["id"])
    step_id = str(step["id"])
    approval_required = bool(explanation.get("approval_required"))

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action=AUDIT_AUTO_EXECUTE_ATTEMPT,
        resource_type="operator_action_plan",
        resource_id=plan_id,
        metadata={
            "operatorId": str(operator["id"]),
            "stepId": step_id,
            "executionMode": get_execution_mode(operator),
            "approvalRequired": approval_required,
        },
    )

    if approval_required:
        update_action_plan_status(client, org_id, plan_id, "pending_approval")
        update_operator_session_status(client, org_id, str(session["id"]), "awaiting_approval")
        return {"status": "pending_approval", "step_id": step_id}

    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except Exception:  # noqa: BLE001
        role = "member"
    if explanation.get("admin_required") and role != "admin":
        return None

    workflow_id, parameters = resolve_execution_target(
        client,
        org_id,
        environment,
        stored_plan.get("primary_context") or session.get("primary_context") or {},
        None,
    )
    result = await execute_operator_workflow(
        workflow_id=workflow_id,
        parameters=parameters,
        current_user=current_user,
        org_id=org_id,
        environment=environment,
        settings=settings,
    )
    action_status = "completed" if result.get("status") == "completed" else "running"
    if result.get("approval_required"):
        action_status = "pending_approval"
        update_action_plan_status(client, org_id, plan_id, "pending_approval")
        update_operator_session_status(client, org_id, str(session["id"]), "awaiting_approval")
    else:
        update_action_plan_status(client, org_id, plan_id, "executing")
        update_operator_session_status(client, org_id, str(session["id"]), "executing")

    create_operator_action(
        client,
        org_id=org_id,
        operator_id=str(operator["id"]),
        session_id=str(session["id"]),
        plan_id=plan_id,
        operator_version_id=str(session.get("operator_version_id") or ""),
        step_id=step_id,
        action_type=step.get("step_type") or "execute_workflow",
        status=action_status,
        workflow_run_id=result.get("run_id"),
        created_by=current_user["user_id"],
    )
    return {"status": action_status, "step_id": step_id, "workflow_run_id": result.get("run_id")}

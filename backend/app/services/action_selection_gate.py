"""Part 5 — shared call-time action resolve + schema gate.

Unifies catalog alias resolution and ActionWorkflowSchema checks so workflow
``invoke_tool`` and chat write staging share one membership/schema path.
Does not replace LLM tool_choice or ChatActionMapper scoring (still multi-chooser
for *which* action); it gates *how* a chosen action is resolved and validated.
"""
from __future__ import annotations

from typing import Any

from app.services.action_workflow_validation import WorkflowCheck
from app.services.chat_connector_models import ConnectorActionPlan


def resolve_call_time_action(action: str, *, registered: set[str] | None = None) -> str:
    """Map catalog / bare aliases to the invoke_tool registry key."""
    from app.connectors.action_catalog.tool_aliases import resolve_registry_action

    if registered is None:
        from app.services.tool_service import list_registered_actions

        registered = set(list_registered_actions())
    return resolve_registry_action(str(action or "").strip(), registered)


def schema_for_action(action: str) -> Any:
    """Workflow schema for action or its registry alias (STA-337 outlook→m365)."""
    from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
    from app.connectors.action_catalog.tool_aliases import REGISTRY_ACTION_ALIASES

    key = str(action or "").strip()
    schema = get_workflow_schema(key)
    if schema:
        return schema
    aliased = REGISTRY_ACTION_ALIASES.get(key)
    if aliased:
        return get_workflow_schema(aliased)
    return None


def validate_invoke_args(
    *,
    action: str,
    args: dict[str, Any] | None,
    message: str = "",
    integration: str | None = None,
) -> WorkflowCheck | None:
    """Return clarification when required schema fields are missing; else None."""
    from app.services.action_workflow_validation import validate_plan_against_schema

    resolved = resolve_call_time_action(action)
    schema = schema_for_action(action) or schema_for_action(resolved)
    if not schema:
        return None
    vendor = (integration or resolved.split(".", 1)[0] or "connector").strip()
    plan = ConnectorActionPlan(
        tool_name=resolved.replace(".", "_"),
        invoke_action=resolved,
        integration=vendor,
        kind="write",
        label=schema.intent_label or resolved,
        args=dict(args or {}),
    )
    return validate_plan_against_schema(plan, schema)


def gate_workflow_invoke(
    *,
    action: str,
    args: dict[str, Any] | None,
    message: str = "",
) -> str:
    """Resolve aliases and enforce schema before workflow ``invoke_tool``.

    Returns the registry action to invoke. Raises ``ValueError`` when required
    parameters are missing (fail closed — no blind execute).
    """
    resolved = resolve_call_time_action(action)
    check = validate_invoke_args(action=action, args=args, message=message)
    if check and check.missing:
        missing = ", ".join(check.missing)
        raise ValueError(
            f"action_selection_gate: {resolved} missing required params: {missing}"
        )
    return resolved


def gate_read_preflight(
    *,
    action: str,
    args: dict[str, Any] | None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """F1 READ: compile and validate before provider execution (same gate as ReAct/invoke)."""
    from app.connectors.action_catalog.f1_read_slice import is_f1_read_action
    from app.services.read_preflight import apply_preflight_to_params, preflight_read_action

    resolved = resolve_call_time_action(action)
    if not is_f1_read_action(resolved) and not is_f1_read_action(action):
        return dict(args or {})
    result = preflight_read_action(
        context={
            **(context or {}),
            "action_key": action,
            "proposed_args": dict(args or {}),
        },
    )
    if not result.ok:
        raise ValueError(
            f"action_selection_gate: {resolved} preflight {result.error_class}: {result.blocking_reason}"
        )
    return apply_preflight_to_params(dict(args or {}), result)

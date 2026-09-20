"""2.0-B — compiled F1 READ for department recipes (pipeline, invoices, tickets).

Uses the same sealed HMAC invoke as traffic. Does not execute WRITE recipes.
"""
from __future__ import annotations

from typing import Any

from app.capability_ontology.cognitive_recipe_planner import match_recipe_for_query
from app.capability_ontology.recipe_resolver import resolve_recipe
from app.config import Settings, get_settings
from app.services.clarification_policy import format_not_connected_message
from app.services.connector_semantic_registry import connector_display_name
from app.services.execution_plan_service import execution_plan_patch, reconcile_execution_plan
from app.services.sealed_read_execution import ensure_plan_read_step, invoke_sealed_f1_read
from app.services.tool_types import ToolContext, ToolValidationError

OPERATIONAL_READ_RECIPES = frozenset(
    {
        "sales.pipeline.health",
        "finance.receivables.overdue",
        "support.issue_trends",
    }
)

_RECIPE_VENDOR = {
    "sales.pipeline.health": "hubspot",
    "finance.receivables.overdue": "quickbooks",
    "support.issue_trends": "zendesk",
}

_SEARCH_TO_LIST = {
    "hubspot.deals.search": "hubspot.deals.list",
    "hubspot.contacts.search": "hubspot.contacts.list",
    "hubspot.companies.search": "hubspot.companies.list",
}


def _open_ended_read(message: str) -> bool:
    text = (message or "").lower()
    return not any(
        token in text
        for token in ("named", "filter", "equals", "email@", "deal id", "ticket #")
    )


def _summarize_read(action_key: str, data: Any) -> str:
    payload = data if isinstance(data, dict) else {}
    results = payload.get("results") or payload.get("invoices") or payload.get("tickets") or []
    if isinstance(results, list) and results:
        n = len(results)
        if "deal" in action_key:
            return f"I found {n} deal{'s' if n != 1 else ''} in the connected CRM."
        if "invoice" in action_key:
            return f"I found {n} invoice{'s' if n != 1 else ''} in the connected finance system."
        if "ticket" in action_key:
            return f"I found {n} ticket{'s' if n != 1 else ''} in the connected support system."
        return f"I found {n} matching records."
    total = payload.get("total") or payload.get("count")
    if isinstance(total, (int, float)) and total:
        return f"I found {int(total)} matching records in the connected system."
    return "The connected system returned no matching records for that read."


async def try_operational_read_short_circuit_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Settings | None,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    recipe = match_recipe_for_query(message)
    if recipe is None or recipe.recipe_id not in OPERATIONAL_READ_RECIPES:
        return None
    connected = [str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()]
    expected_vendor = _RECIPE_VENDOR[recipe.recipe_id]
    resolved = resolve_recipe(
        recipe.recipe_id,
        connected_integrations=connected,
        query=message,
    )
    invoke = None
    if resolved is not None:
        invoke = next(
            (
                step
                for step in resolved.steps
                if step.step_type == "invoke_tool" and step.resolved_action
            ),
            None,
        )
    if invoke is None:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": format_not_connected_message(
                expected_vendor,
                display_name=connector_display_name(expected_vendor),
            ),
            "task_state": task_state or {},
            "workflow_status": "connector_not_connected",
            "execution_path": "operational_f1_read",
        }

    action_key = str(invoke.resolved_action)
    if action_key in _SEARCH_TO_LIST and _open_ended_read(message):
        action_key = _SEARCH_TO_LIST[action_key]

    active_settings = settings or get_settings()
    plan = reconcile_execution_plan(
        message=message,
        task_state=task_state,
        capability_id=invoke.capability_id or recipe.recipe_id,
        connected_integrations=connected,
    )
    plan.execution_strategy = "FAST_PATH"
    step = ensure_plan_read_step(
        plan,
        step_id=f"read_{recipe.recipe_id.replace('.', '_')}",
        action_key=action_key,
        connector_id=str(invoke.resolved_vendor or expected_vendor),
        title=invoke.name,
    )
    tool_ctx = ToolContext(
        settings=active_settings,
        client=client,
        org_id=org_id,
        actor_id="operational-f1-read",
        environment_name="production",
        cognitive_invoke=True,
        plan_id=plan.plan_id,
        capability_id=plan.capability_id,
        conversation_id=plan.conversation_id,
    )
    try:
        invoked, proof, _obs = invoke_sealed_f1_read(
            ctx=tool_ctx,
            action_key=action_key,
            user_message=message,
            task_state=task_state or {},
            connected_integrations=connected,
            plan=plan,
            step=step,
            proposed_args={"limit": 25},
            capability_id=plan.capability_id,
        )
    except ToolValidationError as exc:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": str(exc),
            "task_state": {**(task_state or {}), **execution_plan_patch(plan)},
            "workflow_status": "blocked",
            "execution_path": "operational_f1_read",
            "error_class": getattr(exc, "code", None),
        }
    if not proof.ok:
        status = (
            "needs clarification"
            if proof.error_class == "GENUINE_USER_CLARIFICATION_REQUIRED"
            else "blocked"
        )
        return {
            "stop_pipeline": True,
            "dialogue_mode": "clarifying" if status == "needs clarification" else "answer",
            "message": proof.user_message(),
            "task_state": {**(task_state or {}), **execution_plan_patch(plan)},
            "workflow_status": status,
            "execution_path": "operational_f1_read",
            "error_class": proof.error_class,
        }
    if not invoked.success:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": invoked.error_message
            or "I couldn't complete that read. Try reconnecting the system at /connectors.",
            "task_state": {**(task_state or {}), **execution_plan_patch(plan)},
            "workflow_status": "blocked",
            "execution_path": "operational_f1_read",
        }
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": _summarize_read(action_key, invoked.data),
        "task_state": {**(task_state or {}), **execution_plan_patch(plan)},
        "workflow_status": "completed",
        "execution_path": "operational_f1_read",
    }

"""2.0-B — compiled F1 READ for department recipes (pipeline, invoices, tickets).

Uses the same sealed HMAC invoke as traffic. Does not execute WRITE recipes.
"""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from app.capability_ontology.cognitive_recipe_planner import match_recipe_for_query
from app.capability_ontology.recipe_resolver import resolve_recipe
from app.capability_ontology.recipes import get_recipe
from app.config import Settings, get_settings
from app.services.clarification_policy import format_not_connected_message
from app.services.connector_semantic_registry import connector_display_name
from app.services.execution_plan_service import (
    ExecutionObservation,
    ExecutionStep,
    execution_plan_patch,
    mark_plan_terminal,
    observations_patch,
    reconcile_execution_plan,
)
from app.services.provider_result_grounding import evidence_from_observation
from app.services.sealed_read_execution import (
    attributable_read_actor_id,
    ensure_plan_read_step,
    invoke_sealed_f1_read,
)
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


def _result_count(data: Any) -> int:
    payload = data if isinstance(data, dict) else {}
    results = payload.get("results") or payload.get("invoices") or payload.get("tickets") or []
    if isinstance(results, list):
        return len(results)
    total = payload.get("total") or payload.get("count")
    if isinstance(total, (int, float)):
        return int(total)
    return 0


def _summarize_read(action_key: str, data: Any) -> str:
    n = _result_count(data)
    if n <= 0:
        return "The connected system returned no matching records for that read."
    if "deal" in action_key:
        return f"I found {n} deal{'s' if n != 1 else ''} in the connected CRM."
    if "invoice" in action_key:
        return f"I found {n} invoice{'s' if n != 1 else ''} in the connected finance system."
    if "ticket" in action_key:
        return f"I found {n} ticket{'s' if n != 1 else ''} in the connected support system."
    return f"I found {n} matching records."


def _mark_step(plan: Any, step: ExecutionStep, *, status: str, action_key: str) -> ExecutionStep:
    updated = replace(step, status=status, action_key=action_key)  # type: ignore[arg-type]
    plan.steps = [updated if item.step_id == step.step_id else item for item in plan.steps]
    return updated


def _safe_observation(obs: ExecutionObservation, *, action_key: str, result_count: int, invoked: bool) -> ExecutionObservation:
    structured = {
        "action_key": action_key,
        "result_count": result_count,
        "empty": result_count == 0,
        "provider_invoked": invoked,
    }
    if not isinstance(obs, ExecutionObservation):
        return ExecutionObservation(
            step_id=str(getattr(obs, "step_id", "") or "read"),
            connector_id=str(getattr(obs, "connector_id", "") or "unknown"),
            success=bool(getattr(obs, "success", invoked)),
            summary=str(getattr(obs, "summary", "") or "")[:240],
            observation_id=getattr(obs, "observation_id", None),
            plan_id=getattr(obs, "plan_id", None),
            structured=structured,
        )
    return replace(obs, structured=structured, summary=(obs.summary or "")[:240])


async def try_operational_read_short_circuit_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Settings | None,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    recipe = match_recipe_for_query(message)
    if recipe is None or recipe.recipe_id not in OPERATIONAL_READ_RECIPES:
        from app.services.task_continuity import active_task_frame, decide_task_continuity

        if decide_task_continuity(message, task_state) == "continue":
            cap = str((active_task_frame(task_state) or {}).get("capability_id") or "")
            if cap in OPERATIONAL_READ_RECIPES:
                recipe = get_recipe(cap)
        if recipe is None or recipe.recipe_id not in OPERATIONAL_READ_RECIPES:
            return None
    connected = [str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()]
    expected_vendor = _RECIPE_VENDOR[recipe.recipe_id]
    evidence = (
        (task_state or {}).get("provider_result_evidence")
        if isinstance(task_state, dict)
        else None
    )
    from app.services.task_continuity import decide_task_continuity

    if (
        decide_task_continuity(message, task_state) == "continue"
        and isinstance(evidence, dict)
        and evidence.get("provider_invoked")
        and re.search(r"\blarge\b", message or "", re.I)
        and not re.search(r"\d", message or "")
    ):
        count = evidence.get("result_count")
        count_bit = f"those {count} deals" if isinstance(count, int) else "those deals"
        plan = reconcile_execution_plan(
            message=message,
            task_state=task_state,
            capability_id=recipe.recipe_id,
            connected_integrations=connected,
        )
        plan = mark_plan_terminal(plan, "completed")
        return {
            "stop_pipeline": True,
            "dialogue_mode": "clarifying",
            "message": (
                f"I still have {count_bit} from the connected CRM. "
                "What amount should count as large so I can filter them? "
                "I won't guess a cutoff."
            ),
            "task_state": {
                **(task_state or {}),
                **execution_plan_patch(plan),
                "provider_result_evidence": evidence,
            },
            "workflow_status": "needs clarification",
            "execution_path": "operational_f1_read",
            "provider_result_evidence": evidence,
            "selected_action": evidence.get("action_key"),
        }
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
    actor_id = attributable_read_actor_id(user_id) or "operational-f1-read"
    tool_ctx = ToolContext(
        settings=active_settings,
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        environment_name="production",
        cognitive_invoke=True,
        plan_id=plan.plan_id,
        step_id=step.step_id,
        capability_id=plan.capability_id,
        conversation_id=plan.conversation_id,
    )
    try:
        invoked, proof, obs = invoke_sealed_f1_read(
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
        _mark_step(plan, step, status="failed", action_key=action_key)
        plan = mark_plan_terminal(plan, "blocked")
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
        _mark_step(plan, step, status="failed", action_key=action_key)
        plan = mark_plan_terminal(plan, "blocked")
        return {
            "stop_pipeline": True,
            "dialogue_mode": "clarifying" if status == "needs clarification" else "answer",
            "message": proof.user_message(),
            "task_state": {
                **(task_state or {}),
                **execution_plan_patch(plan),
                **observations_patch(
                    [_safe_observation(obs, action_key=action_key, result_count=0, invoked=False)]
                ),
            },
            "workflow_status": status,
            "execution_path": "operational_f1_read",
            "error_class": proof.error_class,
        }
    if not invoked.success:
        _mark_step(plan, step, status="failed", action_key=action_key)
        plan = mark_plan_terminal(plan, "failed")
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": invoked.error_message
            or "I couldn't complete that read. Try reconnecting the system at /connectors.",
            "task_state": {
                **(task_state or {}),
                **execution_plan_patch(plan),
                **observations_patch(
                    [_safe_observation(obs, action_key=action_key, result_count=0, invoked=True)]
                ),
            },
            "workflow_status": "failed",
            "execution_path": "operational_f1_read",
        }
    count = _result_count(invoked.data)
    completed = _mark_step(plan, step, status="completed", action_key=action_key)
    plan = mark_plan_terminal(plan, "completed")
    safe_obs = _safe_observation(obs, action_key=action_key, result_count=count, invoked=True)
    evidence = evidence_from_observation(
        action_key=action_key,
        result_count=count,
        observation_id=safe_obs.observation_id,
        plan_id=plan.plan_id,
        step_id=completed.step_id,
        success=True,
        provider_invoked=True,
    )
    try:
        from app.services.outcome_learning_service import get_outcome_learning_service

        await get_outcome_learning_service(active_settings).record_connector_action_outcome(
            org_id,
            str(invoke.resolved_vendor or expected_vendor),
            action_key,
            "connector_action_executed",
        )
    except Exception:
        pass
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": _summarize_read(action_key, invoked.data),
        "task_state": {
            **(task_state or {}),
            **execution_plan_patch(plan),
            **observations_patch([safe_obs]),
            "provider_result_evidence": evidence,
        },
        "workflow_status": "completed",
        "execution_path": "operational_f1_read",
        "provider_result_evidence": evidence,
        "selected_action": action_key,
    }

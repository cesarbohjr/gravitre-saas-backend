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

_ACTION_TO_OPERATIONAL_RECIPE = {
    "hubspot.deals.list": "sales.pipeline.health",
    "hubspot.deals.search": "sales.pipeline.health",
    "quickbooks.invoices.list": "finance.receivables.overdue",
    "quickbooks.invoices.query": "finance.receivables.overdue",
    "zendesk.tickets.list": "support.issue_trends",
    "zendesk.tickets.search": "support.issue_trends",
}


def infer_operational_recipe_id(task_state: dict[str, Any] | None) -> str | None:
    """Recover department recipe when persisted plans omitted capability_id."""
    state = task_state if isinstance(task_state, dict) else {}
    plan = state.get("execution_plan") if isinstance(state.get("execution_plan"), dict) else {}
    compiled = state.get("compiled_task") if isinstance(state.get("compiled_task"), dict) else {}
    evidence = state.get("provider_result_evidence") if isinstance(state.get("provider_result_evidence"), dict) else {}
    candidates = [
        plan.get("capability_id"),
        compiled.get("capability_id"),
        state.get("capability_id"),
    ]
    action_keys: list[str] = []
    if evidence.get("action_key"):
        action_keys.append(str(evidence.get("action_key")))
    for step in plan.get("steps") or []:
        if isinstance(step, dict) and step.get("action_key"):
            action_keys.append(str(step.get("action_key")))
        elif not isinstance(step, dict):
            action_key = getattr(step, "action_key", None)
            if action_key:
                action_keys.append(str(action_key))
    for key in compiled.get("action_keys") or []:
        action_keys.append(str(key))
    for obs in state.get("execution_observations") or []:
        if not isinstance(obs, dict):
            continue
        structured = obs.get("structured") if isinstance(obs.get("structured"), dict) else {}
        if structured.get("action_key"):
            action_keys.append(str(structured.get("action_key")))
    for action in action_keys:
        mapped = _ACTION_TO_OPERATIONAL_RECIPE.get(action.strip())
        if mapped:
            candidates.append(mapped)
    for cap in candidates:
        text = str(cap or "").strip()
        if text in OPERATIONAL_READ_RECIPES:
            return text
    return None


def evidence_from_task_state(task_state: dict[str, Any] | None) -> dict[str, Any] | None:
    state = task_state if isinstance(task_state, dict) else {}
    evidence = state.get("provider_result_evidence")
    if isinstance(evidence, dict) and evidence.get("provider_invoked"):
        return evidence
    for obs in state.get("execution_observations") or []:
        if not isinstance(obs, dict):
            continue
        structured = obs.get("structured") if isinstance(obs.get("structured"), dict) else {}
        if not structured.get("provider_invoked"):
            continue
        action_key = str(structured.get("action_key") or "")
        if not action_key:
            continue
        return evidence_from_observation(
            action_key=action_key,
            result_count=int(structured.get("result_count") or 0),
            observation_id=obs.get("observation_id"),
            plan_id=obs.get("plan_id"),
            step_id=obs.get("step_id"),
            success=bool(obs.get("success")),
            provider_invoked=True,
        )
    return None


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


def _deal_rows(data: Any) -> list[dict[str, Any]]:
    payload = data if isinstance(data, dict) else {}
    rows = payload.get("results") or []
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        props = row.get("properties") if isinstance(row.get("properties"), dict) else {}
        out.append(
            {
                "id": str(row.get("id") or props.get("hs_object_id") or ""),
                "name": str(props.get("dealname") or row.get("dealname") or "").strip(),
                "stage": str(props.get("dealstage") or row.get("dealstage") or "").strip(),
                "amount": props.get("amount") if props.get("amount") is not None else row.get("amount"),
                "closedate": str(props.get("closedate") or row.get("closedate") or "").strip(),
            }
        )
    return out


def _parse_amount(raw: Any) -> float | None:
    if raw in (None, ""):
        return None
    try:
        return float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _synthesize_pipeline(data: Any, *, pending_auth: str = "") -> str:
    """Grounded CRM synthesis — never invent traffic or missing amounts."""
    rows = _deal_rows(data)
    n = len(rows) or _result_count(data)
    if n <= 0:
        body = (
            "The connected CRM returned no deals in this read.\n"
            "What is happening: I have a live HubSpot connection, but this list is empty.\n"
            "What appears important: I cannot rank pipeline risk without records.\n"
            "What I cannot conclude: revenue, stage mix, or close timing.\n"
            "What is missing: deal rows from HubSpot for this org.\n"
            "What to do next: confirm deals exist in HubSpot, or name a specific pipeline or owner."
        )
        return f"{body}\n\n{pending_auth}".strip() if pending_auth else body
    by_stage: dict[str, int] = {}
    named: list[str] = []
    amounts: list[float] = []
    missing_amount = 0
    missing_stage = 0
    for row in rows:
        stage = row.get("stage") or "unspecified stage"
        if not row.get("stage"):
            missing_stage += 1
        by_stage[stage] = by_stage.get(stage, 0) + 1
        amt = _parse_amount(row.get("amount"))
        if amt is None:
            missing_amount += 1
        else:
            amounts.append(amt)
        name = row.get("name") or ""
        if name:
            named.append(name)
    stage_bits = ", ".join(f"{stage} ({count})" for stage, count in sorted(by_stage.items(), key=lambda kv: (-kv[1], kv[0]))[:8])
    top_stage = max(by_stage.items(), key=lambda kv: kv[1])[0] if by_stage else "unspecified"
    amount_line = (
        f"Among deals with a numeric amount ({len(amounts)} of {n}), the listed total is {sum(amounts):,.0f} in HubSpot's amount field."
        if amounts
        else "No numeric amounts were present on these rows, so I am not stating a pipeline value."
    )
    examples = ", ".join(named[:3]) if named else "none named"
    missing_bits = [
        "This read is HubSpot's first-page deal list (limit 25), not a guaranteed complete census.",
    ]
    if missing_amount:
        missing_bits.append(f"{missing_amount} deal(s) have no usable amount.")
    if missing_stage:
        missing_bits.append(f"{missing_stage} deal(s) have no stage.")
    if pending_auth:
        missing_bits.append(pending_auth)
    else:
        missing_bits.append("I am not using Google Analytics or Search Console in this answer.")
    important = (
        f"The largest stage bucket in this sample is {top_stage}."
        if n
        else "There is no stage mix to rank."
    )
    return (
        f"From the connected CRM I received {n} deal{'s' if n != 1 else ''} in this sample.\n"
        f"What is happening: HubSpot returned those records. Stage mix in this sample: {stage_bits or 'not labeled'}. {amount_line}\n"
        f"What appears important: {important} Named examples: {examples}.\n"
        "What I cannot conclude: overall company health, win rate, or traffic — those are not in this deal list.\n"
        f"What is missing: {' '.join(missing_bits)}\n"
        "What to do next: pick a stage, owner, or amount cutoff to inspect, or connect a live traffic source if you need acquisition evidence."
    )


def _summarize_read(action_key: str, data: Any, *, pending_auth: str = "") -> str:
    n = _result_count(data)
    if n <= 0:
        empty = "The connected system returned no matching records for that read."
        return f"{empty}\n\n{pending_auth}".strip() if pending_auth else empty
    if "deal" in action_key:
        return _synthesize_pipeline(data, pending_auth=pending_auth)
    if "invoice" in action_key:
        base = f"I found {n} invoice{'s' if n != 1 else ''} in the connected finance system."
    elif "ticket" in action_key:
        base = f"I found {n} ticket{'s' if n != 1 else ''} in the connected support system."
    else:
        base = f"I found {n} matching records."
    return f"{base}\n\n{pending_auth}".strip() if pending_auth else base


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
        from app.services.capability_evidence_plan import looks_like_ceo_ops_question
        from app.services.task_continuity import decide_task_continuity

        if looks_like_ceo_ops_question(message or ""):
            recipe = get_recipe("sales.pipeline.health")
        elif decide_task_continuity(message, task_state) == "continue":
            cap = infer_operational_recipe_id(task_state)
            if cap in OPERATIONAL_READ_RECIPES:
                recipe = get_recipe(cap)
        if recipe is None or recipe.recipe_id not in OPERATIONAL_READ_RECIPES:
            return None
    connected = [str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()]
    expected_vendor = _RECIPE_VENDOR[recipe.recipe_id]
    evidence = evidence_from_task_state(task_state)
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
        plan.capability_id = plan.capability_id or recipe.recipe_id
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
    plan.capability_id = plan.capability_id or recipe.recipe_id
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
    pending_auth = ""
    try:
        from app.services.capability_evidence_plan import (
            build_capability_evidence_plan,
            looks_like_ceo_ops_question,
            pending_auth_prose,
        )

        if looks_like_ceo_ops_question(message or ""):
            ev_plan = build_capability_evidence_plan(
                message or "",
                connected_integrations=connected,
                settings=active_settings,
            )
            pending_auth = pending_auth_prose(ev_plan)
    except Exception:  # noqa: BLE001
        pending_auth = ""
    summary = _summarize_read(action_key, invoked.data, pending_auth=pending_auth)
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
        "message": summary,
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

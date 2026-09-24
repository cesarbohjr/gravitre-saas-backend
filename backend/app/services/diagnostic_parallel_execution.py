"""3.0-F live diagnostic: parallel sealed READs + honest synthesis.

EXTEND E5 / HMAC. Never a second runtime. WRITEs never enter the batch.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from app.config import Settings, get_settings
from app.connectors.action_catalog.f1_read_slice import catalog_action_key, is_f1_read_action
from app.services.clarification_policy import format_not_connected_message
from app.services.connector_semantic_registry import connector_display_name
from app.services.execution_plan_service import (
    ExecutionObservation,
    ExecutionPlan,
    ExecutionStep,
    execution_plan_patch,
    observations_patch,
)
from app.services.multi_source_diagnostic import (
    build_multi_source_diagnostic_plan,
    conclude_diagnostic,
    match_diagnostic_recipe,
)
from app.services.sealed_read_execution import attributable_read_actor_id, invoke_sealed_f1_read
from app.services.tool_types import ToolContext, ToolValidationError

OPTIONAL_VENDORS = frozenset({"google_analytics", "google_search_console"})

_EXPECTED_VENDORS: dict[str, tuple[str, ...]] = {
    "sales.pipeline.health": ("hubspot", "google_analytics"),
    "finance.receivables.overdue": ("quickbooks",),
    "support.issue_trends": ("zendesk",),
}


def _wants_fresh(message: str) -> bool:
    return bool(
        re.search(
            r"\b(refresh|reload|latest|again|rerun|re-run|recheck|check now)\b",
            message or "",
            re.I,
        )
    )


def _disconnected_notes(plan: ExecutionPlan, connected: list[str]) -> list[str]:
    connected_set = {str(v).strip().lower() for v in connected if str(v).strip()}
    expected = _EXPECTED_VENDORS.get(str(plan.capability_id or ""), ())
    notes: list[str] = []
    for vendor in expected:
        if vendor in connected_set:
            continue
        notes.append(
            format_not_connected_message(
                vendor,
                display_name=connector_display_name(vendor),
            )
        )
    return notes


def _reuse_stored_observations(task_state: dict[str, Any] | None) -> list[ExecutionObservation]:
    state = task_state if isinstance(task_state, dict) else {}
    raw = state.get("execution_observations") if isinstance(state.get("execution_observations"), list) else []
    out: list[ExecutionObservation] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        structured = row.get("structured") if isinstance(row.get("structured"), dict) else {}
        out.append(
            ExecutionObservation(
                observation_id=str(row.get("observation_id") or "") or None,
                step_id=str(row.get("step_id") or ""),
                plan_id=str(row.get("plan_id") or "") or None,
                connector_id=str(row.get("connector_id") or structured.get("action_key") or "unknown"),
                success=bool(row.get("success")),
                summary=str(row.get("summary") or "")[:500],
                structured=dict(structured),
            )
        )
    return [row for row in out if row.step_id]


def _compose_message(
    *,
    verdict: dict[str, Any],
    missing: list[str],
) -> str:
    parts = [str(verdict.get("message") or "").strip()]
    if missing:
        parts.append(" ".join(missing))
    return "\n\n".join(part for part in parts if part).strip()


def _grounded_observation(
    *,
    action_key: str,
    invoked: Any,
    obs: ExecutionObservation,
    proof_ok: bool,
) -> tuple[str, dict[str, Any]]:
    from app.services.operational_read_execution import _result_count, _summarize_read

    structured = dict(obs.structured or {})
    structured["action_key"] = action_key
    structured["provider_invoked"] = bool(proof_ok and getattr(invoked, "success", False))
    count = _result_count(getattr(invoked, "data", None))
    structured["result_count"] = count
    if obs.observation_id:
        structured["observation_id"] = obs.observation_id
    if proof_ok and getattr(invoked, "success", False):
        summary = _summarize_read(action_key, invoked.data)
    else:
        summary = str(getattr(invoked, "error_message", None) or obs.summary or "read failed")
    first_line = str(summary or "").split("\n", 1)[0].strip()
    return first_line[:500], structured


def _budget_from_state(task_state: dict[str, Any] | None):
    from app.services.f2_read_repair import RepairBudget

    state = task_state if isinstance(task_state, dict) else {}
    raw = state.get("repair_budget")
    if isinstance(raw, dict):
        return RepairBudget.from_dict(raw)
    return RepairBudget.fresh()


def _existing_diagnostic_plan(task_state: dict[str, Any] | None) -> ExecutionPlan | None:
    state = task_state if isinstance(task_state, dict) else {}
    plan = ExecutionPlan.from_dict(state.get("execution_plan"))
    if plan is None:
        return None
    if str(plan.source or "") != "multi_source_diagnostic":
        return None
    return plan


def _invoke_evidence_step(
    step: ExecutionStep,
    ctx: dict[str, Any],
) -> ExecutionObservation:
    plan: ExecutionPlan = ctx["plan"]
    connected: list[str] = list(ctx.get("connected") or [])
    vendor = str(step.connector_id or "").strip().lower()
    action_key = catalog_action_key(str(step.action_key or ""))
    if vendor and vendor not in {str(v).strip().lower() for v in connected}:
        return ExecutionObservation(
            step_id=step.step_id,
            plan_id=plan.plan_id,
            connector_id=vendor or "unknown",
            success=False,
            summary=format_not_connected_message(
                vendor,
                display_name=connector_display_name(vendor),
            ),
            structured={"action_key": action_key, "provider_invoked": False, "missing_source": True},
        )
    if not action_key or not is_f1_read_action(action_key):
        return ExecutionObservation(
            step_id=step.step_id,
            plan_id=plan.plan_id,
            connector_id=vendor or "unknown",
            success=False,
            summary="That source is not available as a sealed READ on this plan.",
            structured={"action_key": action_key, "provider_invoked": False},
        )
    tool_ctx: ToolContext = ctx["tool_ctx"]
    try:
        invoked, proof, obs = invoke_sealed_f1_read(
            ctx=tool_ctx,
            action_key=action_key,
            user_message=str(ctx.get("message") or ""),
            task_state=ctx.get("task_state") or {},
            connected_integrations=connected,
            plan=plan,
            step=step,
            proposed_args={"limit": 25},
            capability_id=plan.capability_id,
        )
    except ToolValidationError as exc:
        return ExecutionObservation(
            step_id=step.step_id,
            plan_id=plan.plan_id,
            connector_id=vendor or "unknown",
            success=False,
            summary=str(exc),
            error=getattr(exc, "code", None),
            structured={"action_key": action_key, "provider_invoked": False},
        )
    if not proof.ok:
        from app.services.f2_read_repair import emit_f2_repair_audit, repair_blocked_read

        budget = ctx.get("repair_budget")
        repaired = repair_blocked_read(
            blocked=proof,
            ctx=tool_ctx,
            invoke_action=action_key,
            args={"limit": 25},
            user_message=str(ctx.get("message") or ""),
            connected_integrations=connected,
            budget=budget,
        )
        if repaired is not None and repaired.preflight is not None and repaired.preflight.ok:
            emit_f2_repair_audit(
                tool_ctx,
                from_action=action_key,
                repaired=repaired,
                budget=budget,
            )
            try:
                invoked, proof, obs = invoke_sealed_f1_read(
                    ctx=tool_ctx,
                    action_key=repaired.action,
                    user_message=str(ctx.get("message") or ""),
                    task_state=ctx.get("task_state") or {},
                    connected_integrations=connected,
                    plan=plan,
                    step=step,
                    proposed_args=dict(repaired.args or {"limit": 25}),
                    capability_id=plan.capability_id,
                )
                action_key = catalog_action_key(repaired.action)
            except ToolValidationError as exc:
                return ExecutionObservation(
                    step_id=step.step_id,
                    plan_id=plan.plan_id,
                    connector_id=vendor or "unknown",
                    success=False,
                    summary=str(exc),
                    error=getattr(exc, "code", None),
                    structured={
                        "action_key": action_key,
                        "provider_invoked": False,
                        "repair_attempted": True,
                    },
                )
        if not proof.ok:
            structured = dict(obs.structured or {})
            structured["action_key"] = action_key
            structured["provider_invoked"] = False
            return ExecutionObservation(
                observation_id=obs.observation_id,
                step_id=step.step_id,
                plan_id=plan.plan_id,
                connector_id=obs.connector_id or vendor,
                success=False,
                summary=proof.user_message()[:500],
                error=proof.error_class,
                structured=structured,
            )
    summary, structured = _grounded_observation(
        action_key=action_key,
        invoked=invoked,
        obs=obs,
        proof_ok=bool(proof.ok),
    )
    return ExecutionObservation(
        observation_id=obs.observation_id,
        step_id=step.step_id,
        plan_id=plan.plan_id,
        connector_id=obs.connector_id or vendor,
        success=bool(invoked.success),
        summary=str(summary or "")[:500],
        error=invoked.error_code if not invoked.success else None,
        structured=structured,
    )


async def try_diagnostic_parallel_read_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Settings | None,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    from app.services.cognitive_execution_engine import apply_observations_to_plan, execute_read_steps_parallel
    from app.services.durable_work_session import bind_finished_work, execution_result_from_finished_work
    from app.services.task_continuity import decide_task_continuity

    stored = _reuse_stored_observations(task_state)
    existing = _existing_diagnostic_plan(task_state)
    continuing = decide_task_continuity(message, task_state) == "continue"
    recipe = match_diagnostic_recipe(message or "")
    if recipe is None and not (continuing and existing is not None and any(row.success for row in stored)):
        return None
    connected = [str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()]
    plan = None
    if recipe is not None:
        plan = build_multi_source_diagnostic_plan(
            message,
            connected_integrations=connected,
        )
        if plan is not None and existing is not None and continuing:
            plan.plan_id = existing.plan_id
            plan.continuation_of_plan_id = existing.plan_id
    elif existing is not None:
        plan = existing
    if plan is None:
        return None
    reuse = (
        not _wants_fresh(message or "")
        and continuing
        and any(row.success for row in stored)
    )
    active_settings = settings or get_settings()
    actor_id = attributable_read_actor_id(user_id) or "diagnostic-parallel-read"
    tool_ctx = ToolContext(
        settings=active_settings,
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        environment_name="production",
        cognitive_invoke=True,
        plan_id=plan.plan_id,
        capability_id=plan.capability_id,
        conversation_id=plan.conversation_id,
    )
    repair_budget = _budget_from_state(task_state)
    if reuse:
        observations = stored
        provider_reinvoked = False
    else:
        ctx = {
            "plan": plan,
            "connected": connected,
            "tool_ctx": tool_ctx,
            "message": message,
            "task_state": task_state or {},
            "repair_budget": repair_budget,
        }

        async def _handler(step: ExecutionStep, context: dict[str, Any]) -> ExecutionObservation:
            return await asyncio.to_thread(_invoke_evidence_step, step, context)

        observations = await execute_read_steps_parallel(plan, context=ctx, handler=_handler)
        provider_reinvoked = any(
            isinstance(row.structured, dict) and row.structured.get("provider_invoked")
            for row in observations
        )
    plan = apply_observations_to_plan(plan, observations)
    verdict = conclude_diagnostic(plan, observations)
    missing = _disconnected_notes(plan, connected)
    if isinstance(verdict, dict):
        verdict = {
            **verdict,
            "missing_sources": missing,
            "provider_reinvoked": provider_reinvoked,
        }
    body = _compose_message(verdict=verdict, missing=missing)
    succeeded = any(row.success for row in observations)
    required_expected = [
        vendor
        for vendor in _EXPECTED_VENDORS.get(str(plan.capability_id or ""), ())
        if vendor not in OPTIONAL_VENDORS
    ]
    required_disconnected = [vendor for vendor in required_expected if vendor not in set(connected)]
    required_failed = [
        row
        for row in observations
        if not row.success
        and str(row.connector_id or "").strip().lower() not in OPTIONAL_VENDORS
    ]
    from app.services.execution_plan_service import mark_plan_terminal

    if succeeded and not required_disconnected and not required_failed:
        plan = mark_plan_terminal(plan, "completed")
        title = plan.summary or "Diagnostic"
        success_flag = True
        workflow = "completed"
    elif succeeded:
        plan = mark_plan_terminal(plan, "partial")
        title = "Partial diagnostic"
        success_flag = False
        workflow = "partial"
    else:
        plan = mark_plan_terminal(plan, "blocked")
        title = "Work blocked"
        success_flag = False
        workflow = "blocked"
        if not body:
            body = str(verdict.get("message") or "I don't have enough live system evidence.")
    merged_state = {
        **(task_state or {}),
        **execution_plan_patch(plan),
        **observations_patch(observations),
        "diagnostic_conclusion": verdict,
        "repair_budget": repair_budget.to_dict(),
        "repair_error_memory": list(repair_budget.error_memory),
    }
    merged_state = bind_finished_work(merged_state, body=body, title=title)
    payload = execution_result_from_finished_work(merged_state, body=body, success=success_flag)
    if isinstance(payload, dict):
        from app.core.safe_dict import safe_normalize_stored_dict

        structured = safe_normalize_stored_dict(payload.get("structured"))
        structured["claim_labels"] = verdict.get("labels") or []
        structured["missing_sources"] = missing
        structured["provider_reinvoked"] = provider_reinvoked
        payload["structured"] = structured
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": body,
        "task_state": merged_state,
        "workflow_status": workflow,
        "execution_path": "diagnostic_parallel_read",
        "execution_result": payload,
        "provider_reinvoked": provider_reinvoked,
        "diagnostic_conclusion": verdict,
    }

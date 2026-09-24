"""Natural-language listing READ that can take the classed F2 sibling path.

EXTEND F1 HMAC + F2. Not a second runtime. WRITE never enters this turn.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.connectors.action_catalog.f1_read_slice import catalog_action_key, is_f1_read_action
from app.services.execution_plan_service import (
    ExecutionObservation,
    ExecutionPlan,
    ExecutionStep,
    execution_plan_patch,
    mark_plan_terminal,
    observations_patch,
)
from app.services.f2_read_repair import RepairBudget, emit_f2_repair_audit, repair_blocked_read
from app.services.sealed_read_execution import attributable_read_actor_id, invoke_sealed_f1_read
from app.services.tool_types import ToolContext, ToolValidationError

_LISTING = re.compile(
    r"(?is)\b("
    r"search hubspot deals"
    r"|list (?:all )?(?:my )?(?:the )?(?:hubspot )?deals"
    r"|list hubspot deals"
    r"|show (?:me )?(?:all )?(?:my )?(?:hubspot )?deals"
    r")\b"
)


@dataclass(frozen=True)
class ListingF2Intent:
    provider: str
    search_tool: str
    list_tool: str


def listing_f2_intent(message: str) -> ListingF2Intent | None:
    if not match_listing_f2_intent(message or ""):
        return None
    return ListingF2Intent(
        provider="hubspot",
        search_tool="hubspot.deals.search",
        list_tool="hubspot.deals.list",
    )


_BARE_WRITE = re.compile(r"(?is)\b(create|update|delete|enroll)\b")
_NEGATED_WRITE = re.compile(r"(?is)\bdo not (?:create|update|delete)\b")


def match_listing_f2_intent(message: str) -> bool:
    text = message or ""
    if not _LISTING.search(text):
        return False
    if _BARE_WRITE.search(text) and not _NEGATED_WRITE.search(text):
        return False
    return True


def try_listing_f2_read_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Settings | None,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    if not match_listing_f2_intent(message or ""):
        return None
    connected = [str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()]
    if "hubspot" not in set(connected):
        return None
    from app.services.operational_read_execution import _result_count, _summarize_read

    existing = ExecutionPlan.from_dict((task_state or {}).get("execution_plan"))
    plan_id = existing.plan_id if existing is not None else str(uuid4())
    step = ExecutionStep(
        step_id="read_deals",
        title="List HubSpot deals",
        kind="read",
        connector_id="hubspot",
        capability_id="crm.deals.read",
        action_key="hubspot.deals.search",
    )
    plan = ExecutionPlan(
        plan_id=plan_id,
        summary="List HubSpot deals",
        objective=str(message or "")[:240],
        steps=[step],
        source="listing_f2_read",
        capability_id="crm.deals.read",
        continuation_of_plan_id=existing.plan_id if existing is not None else None,
    )
    if existing is not None:
        plan.plan_id = existing.plan_id
    actor_id = attributable_read_actor_id(user_id) or "listing-f2-read"
    active_settings = settings or get_settings()
    tool_ctx = ToolContext(
        settings=active_settings,
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        environment_name="production",
        cognitive_invoke=True,
        plan_id=plan.plan_id,
        capability_id=plan.capability_id,
    )
    budget = RepairBudget.fresh()
    raw = (task_state or {}).get("repair_budget") if isinstance(task_state, dict) else None
    if isinstance(raw, dict):
        budget = RepairBudget.from_dict(raw)
    action_key = "hubspot.deals.search"
    repaired_used = False
    try:
        invoked, proof, obs = invoke_sealed_f1_read(
            ctx=tool_ctx,
            action_key=action_key,
            user_message=message or "",
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
            "workflow_status": "blocked",
            "execution_path": "listing_f2_read",
            "writes_started": False,
        }
    if not proof.ok:
        repaired = repair_blocked_read(
            blocked=proof,
            ctx=tool_ctx,
            invoke_action=action_key,
            args={"limit": 25},
            user_message=message or "",
            connected_integrations=connected,
            budget=budget,
        )
        if repaired is None or repaired.preflight is None or not repaired.preflight.ok:
            body = proof.user_message()
            plan = mark_plan_terminal(plan, "blocked")
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": body,
                "task_state": {
                    **(task_state or {}),
                    **execution_plan_patch(plan),
                    "repair_budget": budget.to_dict(),
                    "repair_error_memory": list(budget.error_memory),
                },
                "workflow_status": "blocked",
                "execution_path": "listing_f2_read",
                "writes_started": False,
            }
        emit_f2_repair_audit(tool_ctx, from_action=action_key, repaired=repaired, budget=budget)
        invoked, proof, obs = invoke_sealed_f1_read(
            ctx=tool_ctx,
            action_key=repaired.action,
            user_message=message or "",
            task_state=task_state or {},
            connected_integrations=connected,
            plan=plan,
            step=step,
            proposed_args=dict(repaired.args or {"limit": 25}),
            capability_id=plan.capability_id,
        )
        action_key = catalog_action_key(repaired.action)
        repaired_used = True
        if not proof.ok:
            plan = mark_plan_terminal(plan, "blocked")
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": proof.user_message(),
                "task_state": {
                    **(task_state or {}),
                    **execution_plan_patch(plan),
                    "repair_budget": budget.to_dict(),
                    "repair_error_memory": list(budget.error_memory),
                },
                "workflow_status": "blocked",
                "execution_path": "listing_f2_read",
                "writes_started": False,
            }
    if not is_f1_read_action(action_key):
        return None
    count = _result_count(getattr(invoked, "data", None))
    summary = _summarize_read(action_key, invoked.data)
    observation = ExecutionObservation(
        observation_id=obs.observation_id,
        step_id=step.step_id,
        plan_id=plan.plan_id,
        connector_id="hubspot",
        success=bool(invoked.success),
        summary=str(summary).split("\n", 1)[0][:500],
        structured={
            "action_key": action_key,
            "result_count": count,
            "provider_invoked": True,
            "repaired": repaired_used,
        },
    )
    plan = mark_plan_terminal(plan, "completed" if invoked.success else "failed")
    from app.services.durable_work_session import bind_finished_work, execution_result_from_finished_work
    from app.services.provider_result_grounding import evidence_from_observation

    merged = {
        **(task_state or {}),
        **execution_plan_patch(plan),
        **observations_patch([observation]),
        "repair_budget": budget.to_dict(),
        "repair_error_memory": list(budget.error_memory),
    }
    merged = bind_finished_work(merged, body=summary, title="HubSpot deals")
    evidence = evidence_from_observation(
        action_key=action_key,
        result_count=int(count),
        observation_id=observation.observation_id,
        plan_id=plan.plan_id,
        step_id=step.step_id,
        success=bool(invoked.success),
        provider_invoked=True,
    )
    payload = execution_result_from_finished_work(merged, body=summary, success=bool(invoked.success))
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": summary,
        "task_state": merged,
        "workflow_status": "completed" if invoked.success else "failed",
        "execution_path": "listing_f2_read",
        "execution_result": payload,
        "provider_result_evidence": evidence,
        "writes_started": False,
        "repaired": repaired_used,
        "plan_id": plan.plan_id,
    }

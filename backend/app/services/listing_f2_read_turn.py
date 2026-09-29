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

_DEALS = re.compile(
    r"(?is)\b("
    r"search hubspot deals"
    r"|list (?:all )?(?:my )?(?:the )?(?:hubspot )?deals"
    r"|list hubspot deals"
    r"|show (?:me )?(?:all )?(?:my )?(?:hubspot )?deals"
    r")\b"
)
_CONTACTS = re.compile(
    r"(?is)\b("
    r"how many (?:hubspot )?contacts"
    r"|count (?:(?:the|my|our|all) )?(?:hubspot )?contacts"
    r"|hubspot contact(?:s)? count"
    r"|list (?:all )?(?:my )?(?:the )?(?:hubspot )?contacts"
    r"|search hubspot contacts"
    r"|how many.{0,80}hubspot.{0,40}contacts"
    r"|hubspot contacts (?:are|in this|in the|do we)"
    r")\b"
)
_BARE_WRITE = re.compile(r"(?is)\b(create|update|delete|enroll)\b")
_NEGATED_WRITE = re.compile(r"(?is)\bdo not (?:create|update|delete)\b")
_SHOW_BOUND_ARTIFACT = re.compile(
    r"(?is)\b(show|open)\b.{0,40}\b(report|table|artifact|deliverable)\b"
)
_WANTS_FRESH = re.compile(r"(?is)\b(refresh|reload|latest|again|rerun|re-run|recheck)\b")


@dataclass(frozen=True)
class ListingF2Intent:
    provider: str
    search_tool: str
    list_tool: str
    capability_id: str
    title: str
    count_query: bool = False


def listing_f2_intent(message: str) -> ListingF2Intent | None:
    text = message or ""
    if _BARE_WRITE.search(text) and not _NEGATED_WRITE.search(text):
        return None
    if _CONTACTS.search(text):
        wants_count = bool(
            re.search(r"(?is)\b(how many|count)\b", text) or re.search(r"(?is)\bcontact(?:s)? count\b", text)
        )
        return ListingF2Intent(
            provider="hubspot",
            search_tool="hubspot.contacts.search",
            list_tool="hubspot.contacts.list",
            capability_id="crm.contacts.read",
            title="HubSpot contacts",
            count_query=wants_count,
        )
    if _DEALS.search(text):
        return ListingF2Intent(
            provider="hubspot",
            search_tool="hubspot.deals.search",
            list_tool="hubspot.deals.list",
            capability_id="crm.deals.read",
            title="HubSpot deals",
        )
    return None


def match_listing_f2_intent(message: str) -> bool:
    return listing_f2_intent(message) is not None or match_bound_artifact_resume(message)


def match_bound_artifact_resume(message: str) -> bool:
    text = message or ""
    return bool(_SHOW_BOUND_ARTIFACT.search(text) and not _WANTS_FRESH.search(text))


def _listing_artifact_rows(
    *,
    intent: ListingF2Intent,
    action_key: str,
    count: int,
    data: Any,
) -> list[dict[str, Any]]:
    """Observation-backed table rows only. Never invent counts or prices."""
    if intent.count_query:
        object_name = "contacts" if "contact" in action_key else "deals"
        return [
            {
                "system": "HubSpot",
                "object": object_name,
                "count": int(count),
                "source": action_key,
            }
        ]
    payload = data if isinstance(data, dict) else {}
    results = payload.get("results")
    if not isinstance(results, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in results[:25]:
        if not isinstance(row, dict):
            continue
        props = row.get("properties") if isinstance(row.get("properties"), dict) else {}
        if "contact" in action_key:
            rows.append(
                {
                    "id": str(row.get("id") or props.get("hs_object_id") or ""),
                    "email": str(props.get("email") or row.get("email") or "").strip(),
                    "firstname": str(props.get("firstname") or "").strip(),
                    "lastname": str(props.get("lastname") or "").strip(),
                }
            )
        else:
            rows.append(
                {
                    "id": str(row.get("id") or props.get("hs_object_id") or ""),
                    "name": str(props.get("dealname") or row.get("dealname") or "").strip(),
                    "stage": str(props.get("dealstage") or row.get("dealstage") or "").strip(),
                }
            )
    return rows


def try_listing_f2_read_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Settings | None,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any] | None:
    intent = listing_f2_intent(message or "")
    connected = [str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()]
    stored_arts = (task_state or {}).get("work_artifacts") if isinstance(task_state, dict) else None
    stored_deliv = (task_state or {}).get("durable_deliverable") if isinstance(task_state, dict) else None
    if match_bound_artifact_resume(message or "") and (stored_arts or stored_deliv):
        from app.services.durable_work_session import reconstruct_execution_result

        diagnosis = ""
        if isinstance(stored_deliv, dict):
            diagnosis = str(stored_deliv.get("diagnosis") or "")
        reconstructed = reconstruct_execution_result(task_state, body=diagnosis)
        plan = ExecutionPlan.from_dict((task_state or {}).get("execution_plan"))
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": diagnosis
            or str((reconstructed or {}).get("body") or "I still have that finished report."),
            "task_state": dict(task_state or {}),
            "workflow_status": "completed",
            "execution_path": "listing_f2_read_resume",
            "execution_result": reconstructed,
            "provider_reinvoked": False,
            "writes_started": False,
            "plan_id": plan.plan_id if plan is not None else None,
        }
    if intent is None:
        return None
    if "hubspot" not in set(connected):
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": (
                "HubSpot is not connected on this workspace, so I cannot read those records. "
                "Connect HubSpot, then ask again."
            ),
            "workflow_status": "blocked",
            "execution_path": "listing_f2_read",
            "writes_started": False,
        }
    from app.services.operational_read_execution import _result_count, _summarize_read

    existing = ExecutionPlan.from_dict((task_state or {}).get("execution_plan"))
    plan_id = existing.plan_id if existing is not None else str(uuid4())
    step = ExecutionStep(
        step_id="read_listing",
        title=f"Read {intent.title}",
        kind="read",
        connector_id="hubspot",
        capability_id=intent.capability_id,
        action_key=intent.search_tool,
    )
    plan = ExecutionPlan(
        plan_id=plan_id,
        summary=f"Read {intent.title}",
        objective=str(message or "")[:240],
        steps=[step],
        source="listing_f2_read",
        capability_id=intent.capability_id,
        continuation_of_plan_id=existing.plan_id if existing is not None else None,
    )
    if existing is not None:
        plan.plan_id = existing.plan_id
    actor_id = attributable_read_actor_id(user_id) or "listing-f2-read"
    active_settings = settings or get_settings()
    cid = str(conversation_id or "")
    if not cid and isinstance(task_state, dict):
        trace = task_state.get("resolution_trace")
        if isinstance(trace, dict):
            cid = str(trace.get("conversation_id") or "")
        cid = cid or str(task_state.get("conversation_id") or "")
    tool_ctx = ToolContext(
        settings=active_settings,
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        environment_name="production",
        cognitive_invoke=True,
        plan_id=plan.plan_id,
        capability_id=plan.capability_id,
        conversation_id=cid or None,
    )
    budget = RepairBudget.fresh()
    raw = (task_state or {}).get("repair_budget") if isinstance(task_state, dict) else None
    if isinstance(raw, dict):
        budget = RepairBudget.from_dict(raw)
    action_key = intent.search_tool
    repaired_used = False
    proposed_args: dict[str, Any] = {"limit": 25}
    if intent.count_query and "contacts" in intent.search_tool:
        proposed_args = {
            "limit": 1,
            "filter_groups": [
                {"filters": [{"propertyName": "createdate", "operator": "HAS_PROPERTY"}]}
            ],
        }
    try:
        invoked, proof, obs = invoke_sealed_f1_read(
            ctx=tool_ctx,
            action_key=action_key,
            user_message=message or "",
            task_state=task_state or {},
            connected_integrations=connected,
            plan=plan,
            step=step,
            proposed_args=proposed_args,
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
            args=dict(proposed_args),
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
            proposed_args=dict(repaired.args or proposed_args),
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
    if intent.count_query and "contact" in action_key:
        summary = f"This HubSpot account has {count} contact{'s' if count != 1 else ''}."
    else:
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
            "rows": _listing_artifact_rows(
                intent=intent,
                action_key=action_key,
                count=count,
                data=getattr(invoked, "data", None),
            ),
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
    merged = bind_finished_work(merged, body=summary, title=intent.title)
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

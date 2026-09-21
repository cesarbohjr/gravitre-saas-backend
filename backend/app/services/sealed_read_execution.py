"""Sealed F1 READ invoke — plan/step + ActionSpec + HMAC + Observation.

Cognitive traffic/F1 island must not call provider helpers (run_ga4_report)
except as CANONICAL_ADAPTER_INTERNAL inside tool_service / connector modules.

Exception classes (no cognitive plan lineage required):
- health /ops probes
- background connector health
- post-publish marketing metric poll
- billing/marketplace non-chat jobs
- workflow_engine / canvas run invoke_tool (plan_id may be workflow-scoped, not chat ExecutionPlan)
- background_job non-user maintenance
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

from app.connectors.action_catalog.f1_read_slice import catalog_action_key, is_f1_read_action, registry_action_key
from app.core.logging import get_logger
from app.services.canonical_time_resolver import TimeWindow, time_window_from_mapping
from app.services.execution_plan_service import ExecutionObservation, ExecutionPlan, ExecutionStep
from app.services.read_preflight import PreflightResult, preflight_read_action
from app.services.tool_service import invoke_tool
from app.services.tool_types import NormalizedResult, ToolContext, ToolValidationError

logger = get_logger(__name__)

INFRASTRUCTURE_INVOKE_ACTORS = frozenset(
    {
        "health",
        "ops_internal",
        "connector_health",
        "post_publish_marketing",
        "marketplace",
        "billing",
        "workflow_engine",
        "background_job",
    }
)

COGNITIVE_BYPASS_MODULES = (
    "app/services/analytics_traffic_overview_service.py",
    "app/operators/agent_intelligence.py",
    "app/operators/react_engine.py",
)


def attributable_read_actor_id(user_id: str | None) -> str | None:
    """Return the requesting user's UUID, or None if none is attributable.

    audit_events.actor_id FKs auth.users. Do not mint a random UUID, do not
    impersonate the operator org, and do not use a non-UUID service label.
    """
    raw = str(user_id or "").strip()
    if not raw:
        return None
    try:
        return str(UUID(raw))
    except (TypeError, ValueError):
        return None


def unwrap_report_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    inner = data.get("report")
    if isinstance(inner, dict) and ("metricHeaders" in inner or "rows" in inner or "totals" in inner):
        return inner
    return data


def ensure_plan_read_step(
    plan: ExecutionPlan,
    *,
    step_id: str,
    action_key: str,
    connector_id: str,
    title: str,
) -> ExecutionStep:
    for step in plan.steps:
        if step.step_id == step_id:
            return step
    step = ExecutionStep(
        step_id=step_id,
        title=title,
        kind="read",
        action_key=action_key,
        connector_id=connector_id,
        status="pending",
        capability_id=plan.capability_id,
    )
    plan.steps.append(step)
    return step


def invoke_sealed_f1_read(
    *,
    ctx: ToolContext,
    action_key: str,
    user_message: str,
    task_state: dict[str, Any] | None,
    connected_integrations: list[str] | None,
    plan: ExecutionPlan,
    step: ExecutionStep,
    proposed_args: dict[str, Any] | None = None,
    time_window_override: TimeWindow | dict[str, Any] | None = None,
    capability_id: str | None = None,
) -> tuple[NormalizedResult, PreflightResult, ExecutionObservation]:
    """Compile + HMAC + invoke_tool. ReAct args are proposals only."""
    catalog = catalog_action_key(action_key)
    if not is_f1_read_action(catalog):
        raise ToolValidationError("sealed read requires an F1 ActionSpec", code="ACTION_UNAVAILABLE")
    window = time_window_override
    if isinstance(window, dict):
        window = time_window_from_mapping(window)
    bound = replace(
        ctx,
        plan_id=plan.plan_id,
        step_id=step.step_id,
        cognitive_invoke=True,
        capability_id=capability_id or plan.capability_id,
        conversation_id=ctx.conversation_id or plan.conversation_id,
    )
    proof = preflight_read_action(
        execution_plan=plan,
        execution_step=step,
        context={
            "action_key": catalog,
            "capability_id": capability_id or plan.capability_id,
            "org_id": bound.org_id,
            "client": bound.client,
            "settings": bound.settings,
            "user_message": user_message,
            "task_state": task_state or {},
            "connected_integrations": list(connected_integrations or []),
            "environment_name": bound.environment_name,
            "proposed_args": dict(proposed_args or {}),
            "plan_id": plan.plan_id,
            "step_id": step.step_id,
            "turn_id": bound.turn_id or plan.turn_id,
            "time_window_override": window,
        },
    )
    if not proof.ok:
        obs = ExecutionObservation(
            observation_id=str(uuid4()),
            step_id=step.step_id,
            plan_id=plan.plan_id,
            connector_id=proof.connector_id or catalog.split(".", 1)[0],
            success=False,
            summary=proof.user_message(),
            error=proof.error_class,
            capability_id=proof.capability_id,
            resource=str((proof.resource or {}).get("id") or ""),
            structured={"preflight": proof.as_dict()},
        )
        return (
            NormalizedResult(
                success=False,
                action=registry_action_key(catalog),
                error_code=proof.error_class,
                error_message=proof.user_message(),
            ),
            proof,
            obs,
        )
    invoked = invoke_tool(
        replace(bound, preflight_result=proof),
        registry_action_key(catalog),
        dict(proof.compiled_parameters),
    )
    report = unwrap_report_payload(invoked.data) if invoked.success else {}
    obs = ExecutionObservation(
        observation_id=str(uuid4()),
        step_id=step.step_id,
        plan_id=plan.plan_id,
        connector_id=invoked.connector_id or proof.connector_id,
        success=bool(invoked.success),
        summary=(invoked.error_message or "ok")[:500],
        error=invoked.error_code if not invoked.success else None,
        capability_id=proof.capability_id,
        resource=str(proof.compiled_parameters.get("property_id") or proof.compiled_parameters.get("site_url") or ""),
        latency_ms=invoked.latency_ms,
        structured={
            "action_key": catalog,
            "compiled_parameters": dict(proof.compiled_parameters),
            "report": report,
            "time_window": proof.time_window,
        },
    )
    return invoked, proof, obs

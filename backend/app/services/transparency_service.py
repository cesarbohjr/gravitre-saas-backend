"""EU AI Act agent decision transparency logs (STA-112)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.compliance_service import redact_metadata
from app.workflows.audit import write_audit_event

AUDIT_TRANSPARENCY_CREATED = "enterprise.transparency.decision_logged"
AUDIT_TRANSPARENCY_EXPORT = "enterprise.transparency.exported"

_STATUS_MAP = {
    "completed": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
    "paused": "failed",
    "pending_approval": "pending_approval",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_log(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id")),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
        "decisionSource": row.get("decision_source"),
        "operatorId": str(row["operator_id"]) if row.get("operator_id") else None,
        "operatorSessionId": str(row["operator_session_id"]) if row.get("operator_session_id") else None,
        "actionPlanId": str(row["action_plan_id"]) if row.get("action_plan_id") else None,
        "workflowRunId": str(row["workflow_run_id"]) if row.get("workflow_run_id") else None,
        "actorId": str(row["actor_id"]) if row.get("actor_id") else None,
        "inputContext": row.get("input_context") or {},
        "modelInfo": row.get("model_info") or {},
        "toolsInvoked": row.get("tools_invoked") or [],
        "humanOverride": row.get("human_override"),
        "outcome": row.get("outcome") or {},
        "status": row.get("status"),
    }


def model_info_from_plan(stored_plan: dict[str, Any]) -> dict[str, Any]:
    guardrails = stored_plan.get("guardrails") if isinstance(stored_plan.get("guardrails"), dict) else {}
    ai_model = guardrails.get("aiModel") if isinstance(guardrails.get("aiModel"), dict) else {}
    if ai_model:
        return dict(ai_model)
    return {}


def build_input_context(
    *,
    operator: dict[str, Any],
    stored_plan: dict[str, Any],
    step: dict[str, Any],
    session: dict[str, Any],
    execution_mode: str,
) -> dict[str, Any]:
    explanation = step.get("explanation") if isinstance(step.get("explanation"), dict) else {}
    return {
        "operatorId": str(operator.get("id")),
        "operatorName": operator.get("name"),
        "executionMode": execution_mode,
        "planId": str(stored_plan.get("id")),
        "planTitle": stored_plan.get("title"),
        "planSummary": stored_plan.get("summary"),
        "stepId": str(step.get("id")),
        "stepType": step.get("step_type"),
        "stepTitle": step.get("title"),
        "stepExplanation": explanation,
        "sessionId": str(session.get("id")),
        "primaryContext": stored_plan.get("primary_context") or session.get("primary_context") or {},
    }


def create_decision_log(
    client: Any,
    *,
    org_id: str,
    actor_id: str,
    decision_source: str,
    input_context: dict[str, Any],
    model_info: dict[str, Any] | None = None,
    operator_id: str | None = None,
    operator_session_id: str | None = None,
    action_plan_id: str | None = None,
    workflow_run_id: str | None = None,
    human_override: dict[str, Any] | None = None,
    outcome: dict[str, Any] | None = None,
    status: str = "in_progress",
) -> dict[str, Any]:
    row = {
        "org_id": org_id,
        "actor_id": actor_id,
        "decision_source": decision_source,
        "operator_id": operator_id,
        "operator_session_id": operator_session_id,
        "action_plan_id": action_plan_id,
        "workflow_run_id": workflow_run_id,
        "input_context": redact_metadata(input_context, mode="strict"),
        "model_info": redact_metadata(model_info or {}, mode="strict"),
        "human_override": redact_metadata(human_override, mode="strict") if human_override else None,
        "outcome": redact_metadata(outcome or {}, mode="strict"),
        "status": status,
        "updated_at": _now_iso(),
    }
    inserted = client.table("agent_decision_transparency_logs").insert(row).execute()
    if not inserted.data:
        raise RuntimeError("Failed to create transparency log")
    log_row = dict(inserted.data[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_TRANSPARENCY_CREATED,
        resource_type="transparency_log",
        resource_id=str(log_row["id"]),
        metadata={"decisionSource": decision_source, "status": status},
    )
    return _serialize_log(log_row)


def _get_log_row(client: Any, org_id: str, log_id: str) -> dict[str, Any] | None:
    rows = (
        client.table("agent_decision_transparency_logs")
        .select("*")
        .eq("org_id", org_id)
        .eq("id", log_id)
        .limit(1)
        .execute()
        .data
    )
    return dict(rows[0]) if rows else None


def update_decision_log(
    client: Any,
    *,
    org_id: str,
    log_id: str,
    **fields: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"updated_at": _now_iso()}
    if "workflow_run_id" in fields:
        payload["workflow_run_id"] = fields["workflow_run_id"]
    if "status" in fields:
        payload["status"] = fields["status"]
    if "outcome" in fields:
        payload["outcome"] = redact_metadata(fields["outcome"] or {}, mode="strict")
    if "human_override" in fields:
        value = fields["human_override"]
        payload["human_override"] = redact_metadata(value, mode="strict") if value else None
    if "model_info" in fields:
        payload["model_info"] = redact_metadata(fields["model_info"] or {}, mode="strict")
    updated = (
        client.table("agent_decision_transparency_logs")
        .update(payload)
        .eq("org_id", org_id)
        .eq("id", log_id)
        .execute()
    )
    if not updated.data:
        raise ValueError("Transparency log not found")
    return _serialize_log(dict(updated.data[0]))


def append_tool_invocation(
    client: Any,
    *,
    org_id: str,
    log_id: str,
    action: str,
    connector_id: str | None,
    success: bool,
    latency_ms: int | None = None,
    error_code: str | None = None,
) -> None:
    row = _get_log_row(client, org_id, log_id)
    if not row:
        return
    tools = list(row.get("tools_invoked") or [])
    tools.append(
        {
            "action": action,
            "connectorId": connector_id,
            "success": success,
            "latencyMs": latency_ms,
            "errorCode": error_code,
            "at": _now_iso(),
        }
    )
    client.table("agent_decision_transparency_logs").update(
        {"tools_invoked": tools, "updated_at": _now_iso()}
    ).eq("org_id", org_id).eq("id", log_id).execute()


def record_human_override(
    client: Any,
    *,
    org_id: str,
    actor_id: str,
    decision: str,
    comment: str | None = None,
    log_id: str | None = None,
    workflow_run_id: str | None = None,
) -> dict[str, Any] | None:
    row: dict[str, Any] | None = None
    if log_id:
        row = _get_log_row(client, org_id, log_id)
    elif workflow_run_id:
        rows = (
            client.table("agent_decision_transparency_logs")
            .select("*")
            .eq("org_id", org_id)
            .eq("workflow_run_id", workflow_run_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        row = dict(rows[0]) if rows else None
    if not row:
        return None
    override = {
        "decision": decision,
        "actorId": actor_id,
        "comment": comment,
        "recordedAt": _now_iso(),
    }
    return update_decision_log(
        client,
        org_id=org_id,
        log_id=str(row["id"]),
        human_override=override,
    )


def finalize_decision_log_from_run(
    client: Any,
    *,
    org_id: str,
    log_id: str,
    workflow_run_id: str,
    final_status: str,
    errors: list[str] | None = None,
) -> dict[str, Any] | None:
    mapped = _STATUS_MAP.get(final_status, "failed")
    outcome = {
        "workflowRunId": workflow_run_id,
        "runStatus": final_status,
        "errors": errors or [],
    }
    try:
        return update_decision_log(
            client,
            org_id=org_id,
            log_id=log_id,
            workflow_run_id=workflow_run_id,
            status=mapped,
            outcome=outcome,
        )
    except ValueError:
        return None


def list_decision_logs(
    client: Any,
    org_id: str,
    *,
    from_ts: str | None = None,
    to_ts: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    query = (
        client.table("agent_decision_transparency_logs")
        .select("*")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .limit(max(1, min(limit, 200)))
    )
    if from_ts:
        query = query.gte("created_at", from_ts)
    if to_ts:
        query = query.lte("created_at", to_ts)
    rows = query.execute().data or []
    return [_serialize_log(dict(row)) for row in rows]


def build_transparency_export_bundle(
    client: Any,
    org_id: str,
    *,
    actor_id: str,
    from_ts: str | None = None,
    to_ts: str | None = None,
    pii_mode: str = "strict",
) -> dict[str, Any]:
    logs = list_decision_logs(client, org_id, from_ts=from_ts, to_ts=to_ts, limit=500)
    bundle = {
        "orgId": org_id,
        "generatedAt": _now_iso(),
        "window": {"from": from_ts, "to": to_ts},
        "regulation": "EU AI Act — automated decision transparency",
        "decisions": [redact_metadata(log, mode=pii_mode) for log in logs],
        "summary": {
            "decisionCount": len(logs),
            "completed": sum(1 for log in logs if log.get("status") == "completed"),
            "failed": sum(1 for log in logs if log.get("status") == "failed"),
            "pendingApproval": sum(1 for log in logs if log.get("status") == "pending_approval"),
            "withHumanOverride": sum(1 for log in logs if log.get("humanOverride")),
        },
    }
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_TRANSPARENCY_EXPORT,
        resource_type="organization",
        resource_id=org_id,
        metadata={"decisionCount": len(logs), "from": from_ts, "to": to_ts},
    )
    return bundle

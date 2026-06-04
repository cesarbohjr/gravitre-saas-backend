"""Dispatch PagerDuty inbound events to workflow runs (STA-37)."""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.connectors.pagerduty_webhooks import (
    canonical_event_type,
    event_matches_trigger,
    normalize_pagerduty_event,
)
from app.services.execution_service import ExecutionService, get_execution_service
from app.services.devops_workflow_service import (
    devops_workflow_id,
    enrich_devops_incident_parameters,
)
from app.workflows.repository import create_execute_run, get_supabase_client
from app.workflows.schema import compute_run_hash

logger = logging.getLogger(__name__)


def _resolve_triggered_by(client: Any, org_id: str) -> str:
    membership = (
        client.table("organization_members")
        .select("user_id")
        .eq("org_id", org_id)
        .in_("role", ["owner", "admin", "member"])
        .limit(1)
        .execute()
    )
    if membership.data:
        return str(membership.data[0]["user_id"])
    return org_id


def get_pagerduty_triggers(connector: dict[str, Any]) -> list[dict[str, Any]]:
    config = connector.get("config") or {}
    triggers = config.get("pagerduty_triggers")
    return list(triggers) if isinstance(triggers, list) else []


def set_pagerduty_triggers(
    client: Any,
    org_id: str,
    connector_id: str,
    triggers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise ValueError("Connector not found")
    config = dict(row.data[0].get("config") or {})
    config["pagerduty_triggers"] = triggers
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()
    return triggers


def ensure_connector_webhook_secret(
    client: Any,
    org_id: str,
    connector_id: str,
) -> str:
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise ValueError("Connector not found")
    config = dict(row.data[0].get("config") or {})
    secret = (config.get("pagerduty_signing_secret") or config.get("webhook_secret") or "").strip()
    if not secret:
        secret = secrets.token_hex(32)
        config["webhook_secret"] = secret
        client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()
    return secret


def get_connector_webhook_secret(connector: dict[str, Any]) -> str:
    config = connector.get("config") or {}
    return str(
        config.get("pagerduty_signing_secret") or config.get("webhook_secret") or ""
    ).strip()


def _load_active_workflow(client: Any, org_id: str, workflow_id: str) -> dict[str, Any] | None:
    result = (
        client.table("workflow_defs")
        .select("id,name,org_id,status,definition")
        .eq("id", workflow_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    workflow = dict(result.data[0])
    if (workflow.get("status") or "draft") != "active":
        return None
    return workflow


async def start_workflow_from_pagerduty(
    settings: Settings,
    *,
    org_id: str,
    workflow_id: str,
    parameters: dict[str, Any],
    connector_id: str,
    execution_service: ExecutionService | None = None,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    workflow = _load_active_workflow(client, org_id, workflow_id)
    if not workflow:
        return {"workflow_id": workflow_id, "status": "skipped", "reason": "workflow_not_active"}

    definition = workflow.get("definition") or {"schema_version": "v1", "steps": []}
    triggered_by = _resolve_triggered_by(client, org_id)
    run_hash = compute_run_hash(definition, parameters, str(definition.get("schema_version") or "v1"))

    created_run = create_execute_run(
        client=client,
        org_id=org_id,
        workflow_id=workflow_id,
        triggered_by=triggered_by,
        definition_snapshot=definition,
        parameters=parameters,
        run_hash=run_hash,
        status="running",
        approval_status="approved",
        required_approvals=0,
        approver_roles=[],
        environment_name="production",
        trigger_type="pagerduty",
    )
    run_id = str(created_run["id"])
    svc = execution_service or get_execution_service()

    try:
        result = await svc.execute_workflow(
            org_id=org_id,
            workflow_id=workflow_id,
            run_id=run_id,
            parameters=parameters,
            user_id=triggered_by,
            definition=definition,
            environment_name="production",
        )
        update_payload: dict[str, Any] = {"status": result.status}
        if result.status == "failed":
            failed_step = next((item for item in result.results if item.status == "failed"), None)
            update_payload["error_message"] = failed_step.error if failed_step else "Execution failed"
        if result.status in {"completed", "failed", "cancelled"}:
            update_payload["completed_at"] = datetime.now(timezone.utc).isoformat()
        client.table("workflow_runs").update(update_payload).eq("id", run_id).execute()
        return {
            "workflow_id": workflow_id,
            "run_id": run_id,
            "status": result.status,
            "connector_id": connector_id,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "pagerduty_workflow_execution_failed workflow_id=%s run_id=%s error=%s",
            workflow_id,
            run_id,
            exc,
        )
        client.table("workflow_runs").update(
            {
                "status": "failed",
                "error_message": str(exc),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", run_id).execute()
        return {
            "workflow_id": workflow_id,
            "run_id": run_id,
            "status": "failed",
            "connector_id": connector_id,
            "error": str(exc),
        }


async def process_pagerduty_event_batch(
    settings: Settings,
    connector_id: str,
    events: list[dict[str, Any]],
    *,
    execution_service: ExecutionService | None = None,
) -> list[dict[str, Any]]:
    client = get_supabase_client(settings)
    row = (
        client.table("connectors")
        .select("id,org_id,type,status,config,environment")
        .eq("id", connector_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        logger.info("pagerduty_trigger_no_connector connector_id=%s", connector_id)
        return []

    connector = dict(row.data[0])
    if str(connector.get("type") or "").lower() != "pagerduty":
        logger.info("pagerduty_trigger_wrong_type connector_id=%s", connector_id)
        return []

    org_id = str(connector["org_id"])
    triggers = get_pagerduty_triggers(connector)
    if not triggers:
        return []

    outcomes: list[dict[str, Any]] = []
    for event in events:
        wrapped = event.get("event") if isinstance(event.get("event"), dict) else event
        raw_type = str(
            (wrapped.get("event_type") if isinstance(wrapped, dict) else None)
            or event.get("event")
            or event.get("event_type")
            or event.get("type")
            or ""
        )
        event_type = canonical_event_type(raw_type) or raw_type
        if not event_type:
            continue

        matching = [t for t in triggers if event_matches_trigger(t, event_type=event_type)]
        if not matching:
            continue

        normalized = normalize_pagerduty_event(event)
        for trigger in matching:
            if not trigger.get("id"):
                trigger = {**trigger, "id": str(uuid.uuid4())}
            workflow_id = str(trigger["workflow_id"])
            parameters = {**normalized, "trigger": dict(trigger)}
            if workflow_id == devops_workflow_id(org_id):
                workflow = _load_active_workflow(client, org_id, workflow_id)
                if workflow:
                    parameters = enrich_devops_incident_parameters(parameters, workflow)
            result = await start_workflow_from_pagerduty(
                settings,
                org_id=org_id,
                workflow_id=workflow_id,
                parameters=parameters,
                connector_id=connector_id,
                execution_service=execution_service,
            )
            outcomes.append(result)

    return outcomes

"""Dispatch Salesforce inbound events to workflow runs (STA-32)."""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.connectors.salesforce import get_lead, get_opportunity
from app.connectors.salesforce_oauth import ensure_salesforce_session
from app.connectors.salesforce_webhooks import (
    canonical_event_type,
    event_matches_trigger,
    normalize_salesforce_event,
)
from app.services.execution_service import ExecutionService, get_execution_service
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


def get_salesforce_triggers(connector: dict[str, Any]) -> list[dict[str, Any]]:
    config = connector.get("config") or {}
    triggers = config.get("salesforce_triggers")
    return list(triggers) if isinstance(triggers, list) else []


def set_salesforce_triggers(
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
    config["salesforce_triggers"] = triggers
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
    secret = (config.get("webhook_secret") or "").strip()
    if not secret:
        secret = secrets.token_hex(32)
        config["webhook_secret"] = secret
        client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()
    return secret


def get_connector_webhook_secret(connector: dict[str, Any]) -> str:
    config = connector.get("config") or {}
    return str(config.get("webhook_secret") or "").strip()


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


def _enrich_normalized_record(
    normalized: dict[str, Any],
    *,
    instance_url: str,
    access_token: str,
    event_type: str,
) -> None:
    sf_event = normalized.get("salesforce_event") or {}
    record_id = sf_event.get("recordId")
    if not record_id:
        return
    try:
        if event_type.startswith("lead.") and normalized.get("lead"):
            record = get_lead(instance_url, access_token, str(record_id))
            normalized["lead"] = {
                "id": str(record.get("Id") or record_id),
                "fields": {k: v for k, v in record.items() if k != "attributes"},
            }
        elif event_type.startswith("opportunity.") and normalized.get("opportunity"):
            record = get_opportunity(instance_url, access_token, str(record_id))
            normalized["opportunity"] = {
                "id": str(record.get("Id") or record_id),
                "fields": {k: v for k, v in record.items() if k != "attributes"},
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("salesforce_trigger_enrich_failed type=%s error=%s", event_type, exc)


async def start_workflow_from_salesforce(
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
        trigger_type="salesforce",
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
        # Module A: execute_workflow_steps already finalized — do not re-write workflow_runs.
        return {
            "workflow_id": workflow_id,
            "run_id": run_id,
            "status": result.status,
            "connector_id": connector_id,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "salesforce_workflow_execution_failed workflow_id=%s run_id=%s error=%s",
            workflow_id,
            run_id,
            exc,
        )
        from app.services.trigger_run_finalize import finalize_trigger_exception

        finalize_trigger_exception(
            client,
            org_id=org_id,
            run_id=run_id,
            actor_id=triggered_by,
            workflow_id=workflow_id,
            error=str(exc),
            source="salesforce_trigger",
        )
        return {
            "workflow_id": workflow_id,
            "run_id": run_id,
            "status": "failed",
            "connector_id": connector_id,
            "error": str(exc),
        }


async def process_salesforce_event_batch(
    settings: Settings,
    connector_id: str,
    events: list[dict[str, Any]],
    *,
    execution_service: ExecutionService | None = None,
) -> list[dict[str, Any]]:
    """Process Salesforce webhook batch for a single connector."""
    client = get_supabase_client(settings)
    row = (
        client.table("connectors")
        .select("id,org_id,type,status,config,environment")
        .eq("id", connector_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        logger.info("salesforce_trigger_no_connector connector_id=%s", connector_id)
        return []

    connector = dict(row.data[0])
    if str(connector.get("type") or "").lower() != "salesforce":
        logger.info("salesforce_trigger_wrong_type connector_id=%s", connector_id)
        return []

    org_id = str(connector["org_id"])
    triggers = get_salesforce_triggers(connector)
    if not triggers:
        return []

    outcomes: list[dict[str, Any]] = []
    token, instance_url, token_err = ensure_salesforce_session(
        client,
        org_id,
        connector_id,
        settings,
        environment_name=connector.get("environment"),
    )

    for event in events:
        raw_type = str(
            event.get("event")
            or event.get("eventType")
            or event.get("type")
            or ""
        )
        event_type = canonical_event_type(raw_type) or raw_type
        if not event_type:
            continue

        stage_name = (
            event.get("stageName")
            or event.get("stage_name")
            or event.get("StageName")
            or event.get("propertyValue")
        )
        matching = [
            t
            for t in triggers
            if event_matches_trigger(
                t,
                event_type=event_type,
                stage_name=str(stage_name) if stage_name is not None else None,
            )
        ]
        if not matching:
            continue

        normalized = normalize_salesforce_event(event)
        if token and instance_url:
            _enrich_normalized_record(
                normalized,
                instance_url=instance_url,
                access_token=token,
                event_type=event_type,
            )
        elif token_err:
            normalized["salesforce_token_error"] = token_err

        for trigger in matching:
            workflow_id = str(trigger["workflow_id"])
            parameters = {**normalized, "trigger": dict(trigger)}
            result = await start_workflow_from_salesforce(
                settings,
                org_id=org_id,
                workflow_id=workflow_id,
                parameters=parameters,
                connector_id=connector_id,
                execution_service=execution_service,
            )
            outcomes.append(result)

    return outcomes


def on_salesforce_connector_connected(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
) -> None:
    """After OAuth: ensure per-connector webhook secret for inbound verification."""
    _ = settings
    try:
        ensure_connector_webhook_secret(client, org_id, connector_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "salesforce_webhook_secret_failed org_id=%s connector_id=%s error=%s",
            org_id,
            connector_id,
            exc,
        )

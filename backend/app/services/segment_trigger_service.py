"""Dispatch Segment inbound events to workflow runs (STA-69)."""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.connectors.segment_webhooks import (
    canonical_event_type,
    event_matches_trigger,
    normalize_segment_event,
)
from app.services.execution_service import ExecutionService
from app.services.marketo_workflow_service import webinar_followup_workflow_id
from app.workflows.repository import get_supabase_client
from app.core.safe_dict import safe_normalize_stored_dict

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


def get_segment_triggers(connector: dict[str, Any]) -> list[dict[str, Any]]:
    config = connector.get("config") or {}
    triggers = config.get("segment_triggers")
    return list(triggers) if isinstance(triggers, list) else []


def set_segment_triggers(
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
    config = safe_normalize_stored_dict(row.data[0], key='config')
    config["segment_triggers"] = triggers
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
    config = safe_normalize_stored_dict(row.data[0], key='config')
    secret = (config.get("segment_webhook_secret") or config.get("webhook_secret") or "").strip()
    if not secret:
        secret = secrets.token_hex(32)
        config["webhook_secret"] = secret
        config["segment_webhook_secret"] = secret
        client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()
    return secret


def get_connector_webhook_secret(connector: dict[str, Any]) -> str:
    config = connector.get("config") or {}
    return str(config.get("segment_webhook_secret") or config.get("webhook_secret") or "").strip()


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


async def start_workflow_from_segment(
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
    from app.services.event_triggered_runs import start_event_triggered_run

    outcome = await start_event_triggered_run(
        settings,
        client,
        org_id=org_id,
        workflow_id=workflow_id,
        definition=definition,
        parameters=parameters,
        actor_id=triggered_by,
        trigger_type="segment",
        source="segment_trigger",
        execution_service=execution_service,
    )
    return {**outcome, "connector_id": connector_id}


async def process_segment_event_batch(
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
        logger.info("segment_trigger_no_connector connector_id=%s", connector_id)
        return []

    connector = dict(row.data[0])
    if str(connector.get("type") or "").lower() != "segment":
        logger.info("segment_trigger_wrong_type connector_id=%s", connector_id)
        return []

    org_id = str(connector["org_id"])
    triggers = get_segment_triggers(connector)
    if not triggers:
        return []

    outcomes: list[dict[str, Any]] = []
    for event in events:
        event_type = canonical_event_type(
            str(event.get("type") or event.get("event_type") or event.get("eventType") or "track")
        ) or "track"
        event_name = event.get("event") or event.get("name")
        matching = [
            t
            for t in triggers
            if event_matches_trigger(t, event_type=event_type, event_name=str(event_name) if event_name else None)
        ]
        if not matching:
            continue

        normalized = normalize_segment_event(event)
        for trigger in matching:
            if not trigger.get("id"):
                trigger = {**trigger, "id": str(uuid.uuid4())}
            workflow_id = str(trigger["workflow_id"])
            parameters = {**normalized, "trigger": dict(trigger)}
            if workflow_id == webinar_followup_workflow_id(org_id):
                parameters["webinar_program_id"] = parameters.get("webinar_program_id") or trigger.get("program_id")
                parameters["nurture_list_id"] = parameters.get("nurture_list_id") or trigger.get("nurture_list_id")
                emails = normalized.get("traits", {}).get("email") or normalized.get("properties", {}).get("email")
                if emails:
                    parameters["attendee_emails"] = [emails] if isinstance(emails, str) else emails
            result = await start_workflow_from_segment(
                settings,
                org_id=org_id,
                workflow_id=workflow_id,
                parameters=parameters,
                connector_id=connector_id,
                execution_service=execution_service,
            )
            outcomes.append(result)

    return outcomes

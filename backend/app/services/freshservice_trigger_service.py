"""Freshservice ticket events → workflow runs.

A matched event starts the bound workflow through ``start_event_triggered_run``,
so the run gets the same policy and approval floor as a manual run: a workflow
that changes a ticket (``freshservice.tickets.update_status``) waits for human
approval, and the step reads the ticket back before it reports success.
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.connectors.freshservice_webhooks import (
    event_matches_trigger,
    freshservice_event_id,
    normalize_freshservice_event,
)
from app.core.safe_dict import safe_normalize_stored_dict
from app.services.execution_service import ExecutionService
from app.workflows.repository import get_supabase_client

logger = logging.getLogger(__name__)

SECRET_KEYS: tuple[str, ...] = ("webhook_secret",)


def get_freshservice_triggers(connector: dict[str, Any]) -> list[dict[str, Any]]:
    triggers = (connector.get("config") or {}).get("freshservice_triggers")
    return list(triggers) if isinstance(triggers, list) else []


def set_freshservice_triggers(
    client: Any, org_id: str, connector_id: str, triggers: list[dict[str, Any]]
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
    config = safe_normalize_stored_dict(row.data[0], key="config")
    config["freshservice_triggers"] = triggers
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()
    return triggers


def ensure_connector_webhook_secret(client: Any, org_id: str, connector_id: str) -> str:
    from app.services.connector_webhook_secret_store import ensure_webhook_secret

    return ensure_webhook_secret(
        client, org_id, connector_id, read_keys=SECRET_KEYS, generate_keys=SECRET_KEYS
    )


def get_connector_webhook_secret(connector: dict[str, Any]) -> str:
    from app.services.connector_webhook_secret_store import first_secret

    return first_secret(connector.get("config") or {}, SECRET_KEYS)


def _load_active_workflow(client: Any, org_id: str, workflow_id: str) -> dict[str, Any] | None:
    result = (
        client.table("workflow_defs")
        .select("id,name,org_id,status,definition,created_by")
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


async def start_workflow_from_freshservice(
    settings: Settings,
    *,
    org_id: str,
    workflow_id: str,
    parameters: dict[str, Any],
    connector_id: str,
    execution_service: ExecutionService | None = None,
    provider_event_id: str | None = None,
) -> dict[str, Any]:
    from app.services.automation_actor import (
        NO_ACTOR_REASON,
        configured_by_from_parameters,
        resolve_automation_actor,
    )
    from app.services.event_triggered_runs import start_event_triggered_run

    client = get_supabase_client(settings)
    workflow = _load_active_workflow(client, org_id, workflow_id)
    if not workflow:
        return {"workflow_id": workflow_id, "status": "skipped", "reason": "workflow_not_active"}
    actor = resolve_automation_actor(
        client,
        org_id,
        configured_by=configured_by_from_parameters(parameters),
        workflow_created_by=workflow.get("created_by"),
    )
    if not actor:
        return {"workflow_id": workflow_id, "status": "skipped", "reason": NO_ACTOR_REASON}
    outcome = await start_event_triggered_run(
        settings,
        client,
        org_id=org_id,
        workflow_id=workflow_id,
        definition=workflow.get("definition") or {"schema_version": "v1", "steps": []},
        parameters={**parameters, "connector_id": connector_id},
        actor_id=actor,
        trigger_type="freshservice",
        source="freshservice_trigger",
        execution_service=execution_service,
        provider_event_id=provider_event_id,
    )
    return {**outcome, "connector_id": connector_id}


async def process_freshservice_event_batch(
    settings: Settings,
    connector: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    execution_service: ExecutionService | None = None,
) -> list[dict[str, Any]]:
    org_id = str(connector["org_id"])
    connector_id = str(connector["id"])
    triggers = get_freshservice_triggers(connector)
    if not triggers:
        return []
    outcomes: list[dict[str, Any]] = []
    for event in events:
        normalized = normalize_freshservice_event(event)
        if not normalized:
            outcomes.append({"status": "skipped", "reason": "missing_ticket_id"})
            continue
        status = (normalized.get("ticket") or {}).get("status")
        matching = [t for t in triggers if event_matches_trigger(t, event=normalized["event"], status=status)]
        provider_event_id = freshservice_event_id(event, normalized)
        for trigger in matching:
            outcomes.append(
                await start_workflow_from_freshservice(
                    settings,
                    org_id=org_id,
                    workflow_id=str(trigger["workflow_id"]),
                    parameters={**normalized, "trigger": dict(trigger)},
                    connector_id=connector_id,
                    execution_service=execution_service,
                    provider_event_id=provider_event_id,
                )
            )
    return outcomes

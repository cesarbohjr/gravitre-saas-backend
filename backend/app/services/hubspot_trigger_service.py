"""Dispatch HubSpot inbound events to workflow runs (STA-16)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.connectors.hubspot import get_contact, get_deal
from app.connectors.hubspot_oauth import ensure_hubspot_access_token
from app.connectors.hubspot_webhooks import (
    ensure_app_event_subscriptions,
    event_matches_trigger,
    normalize_hubspot_event,
)
from app.services.execution_service import ExecutionService, get_execution_service
from app.workflows.repository import create_execute_run, get_supabase_client
from app.workflows.schema import compute_run_hash
from app.core.safe_dict import safe_normalize_stored_dict

logger = logging.getLogger(__name__)

# Explicit HubSpot dealstage values only — never invent labels.
_CLOSED_WON_VALUES = frozenset(
    {
        "closedwon",
        "closed_won",
        "closed-won",
        "won",
    }
)
_CLOSED_LOST_VALUES = frozenset(
    {
        "closedlost",
        "closed_lost",
        "closed-lost",
        "lost",
    }
)
CLOSED_WON_DEALSTAGES = _CLOSED_WON_VALUES
CLOSED_LOST_DEALSTAGES = _CLOSED_LOST_VALUES


def map_hubspot_event_to_crm_outcome(event: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any] | None:
    """Return outcome mapping when evidence is explicit; otherwise None (skip)."""
    subscription_type = str(event.get("subscriptionType") or event.get("eventType") or "")
    property_name = str(event.get("propertyName") or "").strip().lower()
    property_value = str(event.get("propertyValue") or "").strip().lower().replace(" ", "")

    if subscription_type.startswith("deal.") and property_name in {"dealstage", "hs_deal_stage"}:
        if property_value in _CLOSED_WON_VALUES:
            deal = normalized.get("deal") or {}
            return {
                "outcome_type": "won",
                "external_record_id": deal.get("id") or str(event.get("objectId") or ""),
            }
        if property_value in _CLOSED_LOST_VALUES:
            deal = normalized.get("deal") or {}
            return {
                "outcome_type": "lost",
                "external_record_id": deal.get("id") or str(event.get("objectId") or ""),
            }
    return None


def maybe_emit_crm_outcome_from_hubspot_event(
    client: Any,
    *,
    org_id: str,
    event: dict[str, Any],
    normalized: dict[str, Any],
) -> dict[str, Any] | None:
    """First production caller for ingest_crm_recommendation_outcome (Phase 5 precondition)."""
    mapped = map_hubspot_event_to_crm_outcome(event, normalized)
    if not mapped:
        return None
    ext_id = str(mapped.get("external_record_id") or "").strip()
    if not ext_id:
        logger.debug("hubspot_crm_outcome_skip_missing_object_id")
        return None
    from app.services.crm_outcome_capture_service import ingest_crm_recommendation_outcome

    try:
        return ingest_crm_recommendation_outcome(
            client,
            org_id=org_id,
            outcome_type=str(mapped["outcome_type"]),
            connector_type="hubspot",
            external_record_id=ext_id,
            metadata={
                "source": "hubspot_webhook",
                "subscriptionType": event.get("subscriptionType") or event.get("eventType"),
                "propertyName": event.get("propertyName"),
                "propertyValue": event.get("propertyValue"),
                "portalId": event.get("portalId"),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("hubspot_crm_outcome_emit_failed org_id=%s err=%s", org_id, exc)
        return None


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


def find_hubspot_connector_by_portal(client: Any, portal_id: int | str) -> dict[str, Any] | None:
    hub_key = str(portal_id)
    result = (
        client.table("connectors")
        .select("id,org_id,type,status,config,environment")
        .eq("type", "hubspot")
        .execute()
    )
    for row in result.data or []:
        config = row.get("config") or {}
        if str(config.get("hub_id")) == hub_key:
            return dict(row)
    return None


def get_hubspot_triggers(connector: dict[str, Any]) -> list[dict[str, Any]]:
    config = connector.get("config") or {}
    triggers = config.get("hubspot_triggers")
    return list(triggers) if isinstance(triggers, list) else []


def set_hubspot_triggers(
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
    config = safe_normalize_stored_dict(row.data[0], key="config")
    config["hubspot_triggers"] = triggers
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()
    return triggers


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
    access_token: str,
    subscription_type: str,
) -> None:
    object_id = (normalized.get("hubspot_event") or {}).get("objectId")
    if not object_id:
        return
    try:
        if subscription_type.startswith("contact.") and normalized.get("contact"):
            record = get_contact(access_token, contact_id=str(object_id))
            normalized["contact"] = {
                "id": str(record.get("id") or object_id),
                "properties": record.get("properties") or {},
            }
        elif subscription_type.startswith("deal.") and normalized.get("deal"):
            record = get_deal(access_token, str(object_id))
            normalized["deal"] = {
                "id": str(record.get("id") or object_id),
                "properties": record.get("properties") or {},
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("hubspot_trigger_enrich_failed type=%s error=%s", subscription_type, exc)


async def start_workflow_from_hubspot(
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
        trigger_type="hubspot",
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
            "hubspot_workflow_execution_failed workflow_id=%s run_id=%s error=%s",
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
            source="hubspot_trigger",
        )
        return {
            "workflow_id": workflow_id,
            "run_id": run_id,
            "status": "failed",
            "connector_id": connector_id,
            "error": str(exc),
        }


async def process_hubspot_event_batch(
    settings: Settings,
    events: list[dict[str, Any]],
    *,
    execution_service: ExecutionService | None = None,
) -> list[dict[str, Any]]:
    """Process HubSpot webhook batch; returns per-workflow dispatch results."""
    client = get_supabase_client(settings)
    outcomes: list[dict[str, Any]] = []

    for event in events:
        portal_id = event.get("portalId")
        subscription_type = str(event.get("subscriptionType") or event.get("eventType") or "")
        property_name = event.get("propertyName")
        if portal_id is None or not subscription_type:
            continue

        connector = find_hubspot_connector_by_portal(client, portal_id)
        if not connector:
            logger.info("hubspot_trigger_no_connector portalId=%s", portal_id)
            continue

        org_id = str(connector["org_id"])
        connector_id = str(connector["id"])
        triggers = get_hubspot_triggers(connector)
        matching = [
            t
            for t in triggers
            if event_matches_trigger(
                t,
                subscription_type=subscription_type,
                property_name=str(property_name) if property_name is not None else None,
            )
        ]

        normalized = normalize_hubspot_event(event)
        # Phase 5 precondition: emit CRM outcomes even when no workflow triggers match
        crm_emit = maybe_emit_crm_outcome_from_hubspot_event(
            client,
            org_id=org_id,
            event=event,
            normalized=normalized,
        )
        if crm_emit:
            logger.info(
                "hubspot_crm_outcome_emitted org_id=%s outcome=%s id=%s",
                org_id,
                crm_emit.get("outcomeType"),
                crm_emit.get("id"),
            )
            outcomes.append(
                {
                    "crm_outcome": crm_emit,
                    "connector_id": connector_id,
                    "status": "crm_outcome_recorded",
                }
            )

        if not matching:
            continue

        access_token, token_err = ensure_hubspot_access_token(
            client,
            org_id,
            connector_id,
            settings,
            environment_name=connector.get("environment"),
            validate_remote=False,
        )
        if access_token:
            _enrich_normalized_record(
                normalized,
                access_token=access_token,
                subscription_type=subscription_type,
            )
        elif token_err:
            normalized["hubspot_token_error"] = token_err

        for trigger in matching:
            workflow_id = str(trigger["workflow_id"])
            parameters = {**normalized, "trigger": dict(trigger)}
            result = await start_workflow_from_hubspot(
                settings,
                org_id=org_id,
                workflow_id=workflow_id,
                parameters=parameters,
                connector_id=connector_id,
                execution_service=execution_service,
            )
            outcomes.append(result)

    return outcomes


def ensure_default_hubspot_triggers_after_oauth(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
) -> None:
    """Bind demo workflow on first HubSpot connect when org seed configured it."""
    _ = settings
    existing_row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if existing_row.data and get_hubspot_triggers(dict(existing_row.data[0])):
        return

    org = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    if not org.data:
        return
    settings_row = org.data[0].get("settings") or {}
    onboarding = settings_row.get("onboarding") if isinstance(settings_row, dict) else {}
    if not isinstance(onboarding, dict):
        return

    workflow_id = onboarding.get("demo_hubspot_workflow_id")
    if not workflow_id:
        return

    triggers = [
        {
            "id": str(uuid.uuid4()),
            "event": "contact.creation",
            "workflow_id": str(workflow_id),
            "active": True,
            "label": "New lead (demo)",
        }
    ]
    set_hubspot_triggers(client, org_id, connector_id, triggers)
    logger.info(
        "hubspot_demo_trigger_installed org_id=%s connector_id=%s workflow_id=%s",
        org_id,
        connector_id,
        workflow_id,
    )


def on_hubspot_connector_connected(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
) -> None:
    """After OAuth: sync app subscriptions (platform) and optional per-org demo bindings."""
    try:
        ensure_app_event_subscriptions(settings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("hubspot_app_subscriptions_sync_failed error=%s", exc)
    try:
        ensure_default_hubspot_triggers_after_oauth(client, org_id, connector_id, settings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("hubspot_default_triggers_failed org_id=%s error=%s", org_id, exc)
    try:
        from app.services.marketing_workflow_service import on_marketing_connectors_updated

        on_marketing_connectors_updated(client, org_id, settings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("marketing_workflow_setup_failed org_id=%s error=%s", org_id, exc)
    try:
        from app.services.council_workflow_service import on_council_workflow_org_ready

        on_council_workflow_org_ready(client, org_id, settings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("council_workflow_setup_failed org_id=%s error=%s", org_id, exc)

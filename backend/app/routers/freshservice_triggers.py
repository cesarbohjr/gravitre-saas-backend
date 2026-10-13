"""Admin API for Freshservice ticket event → workflow trigger bindings."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.connectors.freshservice_webhooks import (
    SECRET_HEADER,
    V1_TRIGGER_EVENTS,
    canonical_event,
    freshservice_inbound_webhook_url,
    normalize_status,
)
from app.core.db import shared_service_client
from app.services.freshservice_trigger_service import (
    ensure_connector_webhook_secret,
    get_freshservice_triggers,
    set_freshservice_triggers,
)

router = APIRouter(prefix="/api/connectors", tags=["freshservice-triggers"])

SAMPLE_PAYLOAD = {
    "event": "ticket.updated",
    "ticket_id": "{{ticket.id_numeric}}",
    "status": "{{ticket.status}}",
    "priority": "{{ticket.priority}}",
    "subject": "{{ticket.subject}}",
    "requester_email": "{{ticket.from_email}}",
    "updated_at": "{{ticket.updated_on}}",
}


class FreshserviceTriggerBinding(BaseModel):
    id: str | None = None
    event: str = Field(..., description="ticket.created, ticket.updated or ticket.status_changed")
    status: str | None = Field(default=None, description="Only when the ticket is in this status")
    workflow_id: str
    active: bool = True
    label: str | None = None


class FreshserviceTriggersUpdate(BaseModel):
    triggers: list[FreshserviceTriggerBinding]


def _load_connector(client: Any, org_id: str, connector_id: str) -> dict[str, Any]:
    row = (
        client.table("connectors")
        .select("id,type,config,deleted_at")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data or row.data[0].get("deleted_at"):
        raise HTTPException(status_code=404, detail="Connector not found")
    connector = dict(row.data[0])
    if str(connector.get("type") or "").lower() != "freshservice":
        raise HTTPException(status_code=400, detail="Not a Freshservice connector")
    return connector


def _setup(settings: Settings, connector_id: str, secret: str) -> dict[str, Any]:
    return {
        "inbound_url": freshservice_inbound_webhook_url(settings, connector_id),
        "webhook_secret": secret,
        "secret_header": SECRET_HEADER,
        "basic_auth": "Alternatively send the secret as the HTTP Basic password (any username).",
        "sample_payload": SAMPLE_PAYLOAD,
    }


@router.get("/{connector_id}/freshservice-triggers")
def list_freshservice_triggers(
    connector_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = shared_service_client(settings, create_client)
    connector = _load_connector(client, org_id, connector_id)
    secret = ensure_connector_webhook_secret(client, org_id, connector_id)
    return {
        "connector_id": connector_id,
        "triggers": get_freshservice_triggers(connector),
        "supported_events": list(V1_TRIGGER_EVENTS),
        **_setup(settings, connector_id, secret),
    }


@router.put("/{connector_id}/freshservice-triggers")
def update_freshservice_triggers(
    connector_id: str,
    body: FreshserviceTriggersUpdate,
    org_id: Annotated[str, Depends(get_org_context)],
    _user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = shared_service_client(settings, create_client)
    _load_connector(client, org_id, connector_id)
    workflow_ids = {item.workflow_id for item in body.triggers}
    if workflow_ids:
        found = (
            client.table("workflow_defs").select("id").eq("org_id", org_id).in_("id", list(workflow_ids)).execute()
        ).data or []
        missing = workflow_ids - {str(r["id"]) for r in found}
        if missing:
            raise HTTPException(status_code=400, detail="Unknown workflow for this organization")
    stored: list[dict[str, Any]] = []
    for item in body.triggers:
        event = canonical_event(item.event)
        if not event:
            raise HTTPException(status_code=400, detail=f"Unsupported event. Use {list(V1_TRIGGER_EVENTS)}")
        stored.append(
            {
                "id": item.id or str(uuid.uuid4()),
                "event": event,
                "status": normalize_status(item.status),
                "workflow_id": item.workflow_id,
                "active": item.active,
                "label": item.label,
                "configured_by": str(_user.get("user_id") or "") or None,
            }
        )
    triggers = set_freshservice_triggers(client, org_id, connector_id, stored)
    secret = ensure_connector_webhook_secret(client, org_id, connector_id)
    return {"connector_id": connector_id, "triggers": triggers, **_setup(settings, connector_id, secret)}

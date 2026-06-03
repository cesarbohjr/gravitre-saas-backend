"""Admin API for PagerDuty → workflow trigger bindings (STA-37)."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.connectors.pagerduty_oauth import normalize_vendor
from app.connectors.pagerduty_webhooks import V1_TRIGGER_EVENTS, pagerduty_inbound_webhook_url
from app.services.pagerduty_trigger_service import (
    ensure_connector_webhook_secret,
    get_pagerduty_triggers,
    set_pagerduty_triggers,
)

router = APIRouter(prefix="/api/connectors", tags=["pagerduty-triggers"])


class PagerDutyTriggerBinding(BaseModel):
    id: str | None = None
    event: str = Field(..., description="incident.triggered or incident.acknowledged")
    workflow_id: str
    active: bool = True
    label: str | None = None


class PagerDutyTriggersUpdate(BaseModel):
    triggers: list[PagerDutyTriggerBinding]


@router.get("/{connector_id}/pagerduty-triggers")
async def list_pagerduty_triggers(
    connector_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = (
        client.table("connectors")
        .select("id,type,config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Connector not found")
    connector = dict(row.data[0])
    if normalize_vendor(str(connector.get("type") or "")) != "pagerduty":
        raise HTTPException(status_code=400, detail="Not a PagerDuty connector")
    secret = ensure_connector_webhook_secret(client, org_id, connector_id)
    return {
        "connector_id": connector_id,
        "triggers": get_pagerduty_triggers(connector),
        "supported_events": list(V1_TRIGGER_EVENTS),
        "inbound_url": pagerduty_inbound_webhook_url(settings, connector_id),
        "webhook_secret": secret,
        "signature_header": "X-PagerDuty-Signature",
    }


@router.put("/{connector_id}/pagerduty-triggers")
async def update_pagerduty_triggers(
    connector_id: str,
    body: PagerDutyTriggersUpdate,
    org_id: Annotated[str, Depends(get_org_context)],
    _user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = (
        client.table("connectors")
        .select("id,type,config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Connector not found")
    connector = dict(row.data[0])
    if normalize_vendor(str(connector.get("type") or "")) != "pagerduty":
        raise HTTPException(status_code=400, detail="Not a PagerDuty connector")

    stored: list[dict[str, Any]] = []
    for item in body.triggers:
        event = (item.event or "").strip()
        if event not in V1_TRIGGER_EVENTS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported event: {event}. Use {list(V1_TRIGGER_EVENTS)}",
            )
        stored.append(
            {
                "id": item.id or str(uuid.uuid4()),
                "event": event,
                "workflow_id": item.workflow_id,
                "active": item.active,
                "label": item.label,
            }
        )

    triggers = set_pagerduty_triggers(client, org_id, connector_id, stored)
    secret = ensure_connector_webhook_secret(client, org_id, connector_id)
    return {
        "connector_id": connector_id,
        "triggers": triggers,
        "inbound_url": pagerduty_inbound_webhook_url(settings, connector_id),
        "webhook_secret": secret,
    }

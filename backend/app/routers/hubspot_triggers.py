"""Admin API for HubSpot → workflow trigger bindings (STA-16)."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.connectors.hubspot_oauth import normalize_vendor
from app.connectors.hubspot_webhooks import V1_SUBSCRIPTION_EVENTS, hubspot_inbound_webhook_url
from app.services.hubspot_trigger_service import get_hubspot_triggers, set_hubspot_triggers

router = APIRouter(prefix="/api/connectors", tags=["hubspot-triggers"])

V1_EVENT_TYPES = [event for event, _prop in V1_SUBSCRIPTION_EVENTS]


class HubSpotTriggerBinding(BaseModel):
    id: str | None = None
    event: str = Field(..., description="HubSpot subscriptionType, e.g. contact.creation")
    workflow_id: str
    property: str | None = Field(
        default=None,
        description="Required for deal.propertyChange (e.g. dealstage)",
    )
    active: bool = True
    label: str | None = None


class HubSpotTriggersUpdate(BaseModel):
    triggers: list[HubSpotTriggerBinding]


@router.get("/{connector_id}/hubspot-triggers")
async def list_hubspot_triggers(
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
    if normalize_vendor(str(connector.get("type") or "")) != "hubspot":
        raise HTTPException(status_code=400, detail="Not a HubSpot connector")
    return {
        "connector_id": connector_id,
        "triggers": get_hubspot_triggers(connector),
        "supported_events": V1_EVENT_TYPES,
        "inbound_url": hubspot_inbound_webhook_url(settings),
    }


@router.put("/{connector_id}/hubspot-triggers")
async def update_hubspot_triggers(
    connector_id: str,
    body: HubSpotTriggersUpdate,
    org_id: Annotated[str, Depends(get_org_context)],
    _user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = (
        client.table("connectors")
        .select("id,type")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Connector not found")
    if normalize_vendor(str(row.data[0].get("type") or "")) != "hubspot":
        raise HTTPException(status_code=400, detail="Not a HubSpot connector")

    normalized: list[dict[str, Any]] = []
    for item in body.triggers:
        if item.event not in V1_EVENT_TYPES and not any(
            item.event == e for e, _ in V1_SUBSCRIPTION_EVENTS
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported event: {item.event}. Supported: {V1_EVENT_TYPES}",
            )
        if item.event == "deal.propertyChange" and not item.property:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="property is required for deal.propertyChange",
            )
        normalized.append(
            {
                "id": item.id or str(uuid.uuid4()),
                "event": item.event,
                "workflow_id": item.workflow_id,
                "property": item.property,
                "active": item.active,
                "label": item.label,
            }
        )

    saved = set_hubspot_triggers(client, org_id, connector_id, normalized)
    return {"connector_id": connector_id, "triggers": saved}

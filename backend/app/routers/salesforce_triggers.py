"""Admin API for Salesforce → workflow trigger bindings (STA-32)."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.connectors.salesforce_oauth import normalize_vendor
from app.connectors.salesforce_webhooks import V1_TRIGGER_EVENTS, salesforce_inbound_webhook_url
from app.services.salesforce_trigger_service import (
    ensure_connector_webhook_secret,
    get_salesforce_triggers,
    set_salesforce_triggers,
)

router = APIRouter(prefix="/api/connectors", tags=["salesforce-triggers"])


class SalesforceTriggerBinding(BaseModel):
    id: str | None = None
    event: str = Field(..., description="e.g. lead.created, opportunity.stageChange")
    workflow_id: str
    stage: str | None = Field(
        default=None,
        description="Optional filter for opportunity.stageChange (StageName value)",
    )
    active: bool = True
    label: str | None = None


class SalesforceTriggersUpdate(BaseModel):
    triggers: list[SalesforceTriggerBinding]


@router.get("/{connector_id}/salesforce-triggers")
async def list_salesforce_triggers(
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
    if normalize_vendor(str(connector.get("type") or "")) != "salesforce":
        raise HTTPException(status_code=400, detail="Not a Salesforce connector")
    secret = ensure_connector_webhook_secret(client, org_id, connector_id)
    return {
        "connector_id": connector_id,
        "triggers": get_salesforce_triggers(connector),
        "supported_events": list(V1_TRIGGER_EVENTS),
        "inbound_url": salesforce_inbound_webhook_url(settings, connector_id),
        "webhook_secret": secret,
        "signature_header": "X-Gravitre-Signature",
    }


@router.put("/{connector_id}/salesforce-triggers")
async def update_salesforce_triggers(
    connector_id: str,
    body: SalesforceTriggersUpdate,
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
    if normalize_vendor(str(row.data[0].get("type") or "")) != "salesforce":
        raise HTTPException(status_code=400, detail="Not a Salesforce connector")

    normalized: list[dict[str, Any]] = []
    for item in body.triggers:
        if item.event not in V1_TRIGGER_EVENTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported event: {item.event}. Supported: {list(V1_TRIGGER_EVENTS)}",
            )
        if item.event == "opportunity.stageChange" and not item.stage:
            pass  # stage filter optional
        normalized.append(
            {
                "id": item.id or str(uuid.uuid4()),
                "event": item.event,
                "workflow_id": item.workflow_id,
                "stage": item.stage,
                "active": item.active,
                "label": item.label,
            }
        )

    ensure_connector_webhook_secret(client, org_id, connector_id)
    saved = set_salesforce_triggers(client, org_id, connector_id, normalized)
    return {
        "connector_id": connector_id,
        "triggers": saved,
        "inbound_url": salesforce_inbound_webhook_url(settings, connector_id),
    }

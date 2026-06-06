"""Admin API for Segment → workflow trigger bindings (STA-69)."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.connectors.segment_connect import normalize_vendor
from app.connectors.segment_webhooks import SUPPORTED_TRIGGER_EVENTS, segment_inbound_webhook_url
from app.services.segment_trigger_service import (
    ensure_connector_webhook_secret,
    get_segment_triggers,
    set_segment_triggers,
)

router = APIRouter(prefix="/api/connectors", tags=["segment-triggers"])


class SegmentTriggerBinding(BaseModel):
    id: str | None = None
    event_type: str = Field(default="track", description="track, identify, group, page, or screen")
    event_name: str | None = Field(default=None, description="Optional track event name filter")
    workflow_id: str
    active: bool = True
    label: str | None = None
    program_id: str | None = None
    nurture_list_id: str | None = None


class SegmentTriggersUpdate(BaseModel):
    triggers: list[SegmentTriggerBinding]


@router.get("/{connector_id}/segment-triggers")
async def list_segment_triggers(
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
    if normalize_vendor(str(connector.get("type") or "")) != "segment":
        raise HTTPException(status_code=400, detail="Not a Segment connector")
    secret = ensure_connector_webhook_secret(client, org_id, connector_id)
    return {
        "connector_id": connector_id,
        "triggers": get_segment_triggers(connector),
        "supported_events": list(SUPPORTED_TRIGGER_EVENTS),
        "inbound_url": segment_inbound_webhook_url(settings, connector_id),
        "webhook_secret": secret,
        "signature_header": "X-Segment-Signature",
        "secret_header": "X-Segment-Webhook-Secret",
    }


@router.put("/{connector_id}/segment-triggers")
async def update_segment_triggers(
    connector_id: str,
    body: SegmentTriggersUpdate,
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
    if normalize_vendor(str(connector.get("type") or "")) != "segment":
        raise HTTPException(status_code=400, detail="Not a Segment connector")

    stored: list[dict[str, Any]] = []
    for item in body.triggers:
        event_type = (item.event_type or "track").strip().lower()
        if event_type not in SUPPORTED_TRIGGER_EVENTS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported event_type: {event_type}. Use {list(SUPPORTED_TRIGGER_EVENTS)}",
            )
        stored.append(
            {
                "id": item.id or str(uuid.uuid4()),
                "event_type": event_type,
                "event_name": item.event_name,
                "workflow_id": item.workflow_id,
                "active": item.active,
                "label": item.label,
                "program_id": item.program_id,
                "nurture_list_id": item.nurture_list_id,
            }
        )

    triggers = set_segment_triggers(client, org_id, connector_id, stored)
    secret = ensure_connector_webhook_secret(client, org_id, connector_id)
    return {
        "connector_id": connector_id,
        "triggers": triggers,
        "inbound_url": segment_inbound_webhook_url(settings, connector_id),
        "webhook_secret": secret,
    }

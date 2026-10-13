"""Freshservice inbound ticket events (Workflow Automator "Trigger Webhook")."""
from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from supabase import create_client

from app.config import Settings, get_settings
from app.connectors.freshservice_webhooks import SECRET_HEADER, flatten_inbound_payload, verify_freshservice_webhook
from app.core.db import shared_service_client
from app.services.event_triggered_runs import raise_if_retryable
from app.services.freshservice_trigger_service import (
    get_connector_webhook_secret,
    process_freshservice_event_batch,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/freshservice", tags=["freshservice-webhooks"])

_MAX_BODY = 256 * 1024
_MAX_EVENTS = 50


@router.post("/inbound/{connector_id}")
async def freshservice_inbound_webhook(
    connector_id: str,
    request: Request,
    x_gravitre_webhook_secret: Annotated[str | None, Header(alias=SECRET_HEADER)] = None,
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    body = await request.body()
    if len(body) > _MAX_BODY:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Payload too large")
    client = shared_service_client(settings, create_client)
    row = (
        client.table("connectors")
        .select("id,org_id,type,status,config,environment,deleted_at")
        .eq("id", connector_id)
        .limit(1)
        .execute()
    )
    connector = dict(row.data[0]) if row.data else None
    # One answer for unknown, deleted and wrong-type connectors: no probing.
    if not connector or connector.get("deleted_at") or str(connector.get("type") or "").lower() != "freshservice":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    secret = get_connector_webhook_secret(connector)
    if not secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook secret not configured")
    if not verify_freshservice_webhook(
        secret=secret, header_secret=x_gravitre_webhook_secret, authorization=authorization
    ):
        logger.warning("freshservice_webhook_auth_invalid connector_id=%s", connector_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")

    try:
        payload = json.loads(body.decode("utf-8")) if body else {}
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON") from exc
    events = flatten_inbound_payload(payload)[:_MAX_EVENTS]
    results = await process_freshservice_event_batch(settings, connector, events)
    raise_if_retryable(results)
    return {"received": len(events), "dispatched": len(results), "results": results}

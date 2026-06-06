"""Segment inbound webhook receiver (STA-69)."""
from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from supabase import create_client

from app.config import Settings, get_settings
from app.connectors.segment_webhooks import (
    flatten_inbound_payload,
    verify_segment_webhook_secret_header,
    verify_segment_webhook_signature,
)
from app.services.segment_trigger_service import (
    get_connector_webhook_secret,
    process_segment_event_batch,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/segment", tags=["segment-webhooks"])


@router.post("/inbound/{connector_id}")
async def segment_inbound_webhook(
    connector_id: str,
    request: Request,
    x_segment_signature: Annotated[str | None, Header(alias="X-Segment-Signature")] = None,
    x_segment_webhook_secret: Annotated[str | None, Header(alias="X-Segment-Webhook-Secret")] = None,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    body = await request.body()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = (
        client.table("connectors")
        .select("id,org_id,type,config")
        .eq("id", connector_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    connector = dict(row.data[0])
    if str(connector.get("type") or "").lower() != "segment":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a Segment connector")

    secret = get_connector_webhook_secret(connector)
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Segment webhook secret not configured",
        )

    verified = verify_segment_webhook_signature(body=body, signature=x_segment_signature, secret=secret)
    if not verified:
        verified = verify_segment_webhook_secret_header(provided=x_segment_webhook_secret, secret=secret)
    if not verified:
        logger.warning("segment_webhook_auth_invalid connector_id=%s", connector_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret or signature")

    try:
        payload = json.loads(body.decode("utf-8")) if body else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON") from exc

    events = flatten_inbound_payload(payload)
    results = await process_segment_event_batch(settings, connector_id, events)
    return {"received": len(events), "dispatched": len(results), "results": results}

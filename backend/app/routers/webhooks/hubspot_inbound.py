"""HubSpot inbound webhook receiver (STA-16)."""
from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.connectors.hubspot_webhooks import verify_hubspot_signature_v3, webhook_client_secret
from app.services.hubspot_trigger_service import process_hubspot_event_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/hubspot", tags=["hubspot-webhooks"])


@router.post("/inbound")
async def hubspot_inbound_webhook(
    request: Request,
    x_hubspot_signature_v3: Annotated[str | None, Header(alias="X-HubSpot-Signature-v3")] = None,
    x_hubspot_request_timestamp: Annotated[str | None, Header(alias="X-HubSpot-Request-Timestamp")] = None,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    body = await request.body()
    secret = webhook_client_secret(settings)
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HubSpot webhook verification is not configured",
        )

    request_uri = str(request.url.path)
    if request.url.query:
        request_uri = f"{request_uri}?{request.url.query}"

    if not verify_hubspot_signature_v3(
        method=request.method,
        request_uri=request_uri,
        body=body,
        timestamp_ms=x_hubspot_request_timestamp,
        signature=x_hubspot_signature_v3,
        client_secret=secret,
    ):
        logger.warning("hubspot_webhook_signature_invalid")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload = json.loads(body.decode("utf-8")) if body else []
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON") from exc

    events: list[dict[str, Any]]
    if isinstance(payload, list):
        events = [dict(item) for item in payload if isinstance(item, dict)]
    elif isinstance(payload, dict):
        events = [payload]
    else:
        events = []

    results = await process_hubspot_event_batch(settings, events)
    return {"received": len(events), "dispatched": len(results), "results": results}

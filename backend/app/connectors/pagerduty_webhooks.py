"""PagerDuty inbound webhooks (STA-37): signature verification and event normalization."""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)

V1_TRIGGER_EVENTS: tuple[str, ...] = (
    "incident.triggered",
    "incident.acknowledged",
)

_EVENT_ALIASES: dict[str, str] = {
    "incident.triggered": "incident.triggered",
    "incident.trigger": "incident.triggered",
    "incident.acknowledged": "incident.acknowledged",
    "incident.acknowledge": "incident.acknowledged",
}


def pagerduty_inbound_webhook_url(settings: Settings, connector_id: str) -> str | None:
    base = (settings.api_public_url or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/api/webhooks/pagerduty/inbound/{connector_id}"


def canonical_event_type(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.strip()
    lowered = key.lower()
    if lowered in _EVENT_ALIASES:
        return _EVENT_ALIASES[lowered]
    if key in _EVENT_ALIASES:
        return _EVENT_ALIASES[key]
    return None


def verify_pagerduty_webhook_signature(
    *,
    body: bytes,
    signature: str | None,
    secret: str,
) -> bool:
    if not signature or not secret:
        return False
    provided = signature.strip()
    v1_sig: str | None = None
    for part in provided.split(","):
        piece = part.strip()
        if piece.startswith("v1="):
            v1_sig = piece[3:]
            break
    if not v1_sig:
        v1_sig = provided.removeprefix("v1=")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1_sig)


def _extract_incident(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data") or event
    if isinstance(data, dict) and "incident" in data:
        inc = data.get("incident")
        return dict(inc) if isinstance(inc, dict) else {}
    if isinstance(data, dict) and data.get("type") == "incident_reference":
        return {"id": data.get("id"), "summary": data.get("summary"), "html_url": data.get("html_url")}
    incident = event.get("incident")
    return dict(incident) if isinstance(incident, dict) else {}


def normalize_pagerduty_event(event: dict[str, Any]) -> dict[str, Any]:
    """Map inbound PagerDuty webhook payload to workflow parameters."""
    wrapped = event.get("event") if isinstance(event.get("event"), dict) else event
    if not isinstance(wrapped, dict):
        wrapped = event

    raw_event = (
        wrapped.get("event_type")
        or wrapped.get("event")
        or event.get("event")
        or event.get("event_type")
    )
    event_type = canonical_event_type(str(raw_event) if raw_event is not None else None) or str(raw_event or "")
    incident = _extract_incident(wrapped) or _extract_incident(event)

    incident_id = incident.get("id") or event.get("incident_id") or event.get("incidentId")
    incident_number = incident.get("incident_number") or incident.get("number")
    summary = incident.get("summary") or incident.get("title")
    urgency = incident.get("urgency")
    status = incident.get("status")
    html_url = incident.get("html_url") or incident.get("htmlUrl")

    normalized: dict[str, Any] = {
        "pagerduty_event": {
            "event": event_type,
            "incidentId": incident_id,
            "incidentNumber": incident_number,
            "summary": summary,
            "urgency": urgency,
            "status": status,
            "htmlUrl": html_url,
            "occurredAt": wrapped.get("occurred_at") or event.get("occurred_at"),
        },
        "incident": {
            "id": incident_id,
            "number": incident_number,
            "summary": summary,
            "urgency": urgency,
            "status": status,
            "html_url": html_url,
        },
    }
    return normalized


def event_matches_trigger(trigger: dict[str, Any], *, event_type: str) -> bool:
    if not trigger.get("active", True):
        return False
    event = canonical_event_type(str(trigger.get("event") or trigger.get("eventType") or ""))
    canonical = canonical_event_type(event_type) or event_type
    if not event or event != canonical:
        return False
    return bool(trigger.get("workflow_id"))


def flatten_inbound_payload(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    messages = payload.get("messages")
    if isinstance(messages, list):
        return [dict(m) for m in messages if isinstance(m, dict)]
    if isinstance(payload.get("event"), dict):
        return [payload]
    return [payload]

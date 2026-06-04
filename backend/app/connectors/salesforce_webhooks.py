"""Salesforce inbound webhooks (STA-32): per-connector HMAC verification and event normalization."""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)

# Canonical event types for trigger bindings
V1_TRIGGER_EVENTS: tuple[str, ...] = (
    "lead.created",
    "opportunity.stageChange",
)

_EVENT_ALIASES: dict[str, str] = {
    "lead.created": "lead.created",
    "lead.creation": "lead.created",
    "lead.create": "lead.created",
    "Lead.created": "lead.created",
    "Lead.Created": "lead.created",
    "opportunity.stagechange": "opportunity.stageChange",
    "opportunity.stage_change": "opportunity.stageChange",
    "opportunity.stageChange": "opportunity.stageChange",
    "Opportunity.stageChange": "opportunity.stageChange",
    "Opportunity.StageChange": "opportunity.stageChange",
}


def salesforce_inbound_webhook_url(settings: Settings, connector_id: str) -> str | None:
    base = (settings.api_public_url or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/api/webhooks/salesforce/inbound/{connector_id}"


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


def verify_salesforce_webhook_signature(
    *,
    body: bytes,
    signature: str | None,
    secret: str,
) -> bool:
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = signature.strip()
    if provided.startswith("sha256="):
        provided = provided[7:]
    return hmac.compare_digest(expected, provided)


def normalize_salesforce_event(event: dict[str, Any]) -> dict[str, Any]:
    """Map inbound payload to workflow run parameters."""
    raw_event = (
        event.get("event")
        or event.get("eventType")
        or event.get("type")
        or event.get("subscriptionType")
    )
    event_type = canonical_event_type(str(raw_event) if raw_event is not None else None) or str(raw_event or "")

    record_id = (
        event.get("recordId")
        or event.get("record_id")
        or event.get("objectId")
        or event.get("object_id")
        or event.get("Id")
    )
    org_id = event.get("organizationId") or event.get("organization_id") or event.get("orgId")
    stage_name = (
        event.get("stageName")
        or event.get("stage_name")
        or event.get("StageName")
        or event.get("propertyValue")
    )
    changed = event.get("changedFields") or event.get("changed_fields") or {}

    normalized: dict[str, Any] = {
        "salesforce_event": {
            "event": event_type,
            "recordId": record_id,
            "organizationId": org_id,
            "stageName": stage_name,
            "changedFields": changed if isinstance(changed, dict) else {},
            "occurredAt": event.get("occurredAt") or event.get("occurred_at"),
            "source": event.get("source"),
        },
    }

    if event_type.startswith("lead."):
        normalized["lead"] = {
            "id": str(record_id) if record_id is not None else None,
            "fields": dict(changed) if isinstance(changed, dict) else {},
        }
    elif event_type.startswith("opportunity."):
        normalized["opportunity"] = {
            "id": str(record_id) if record_id is not None else None,
            "fields": dict(changed) if isinstance(changed, dict) else {},
        }
        if stage_name is not None:
            normalized["opportunity"]["fields"]["StageName"] = stage_name

    return normalized


def event_matches_trigger(
    trigger: dict[str, Any],
    *,
    event_type: str,
    stage_name: str | None,
) -> bool:
    if not trigger.get("active", True):
        return False
    event = canonical_event_type(str(trigger.get("event") or trigger.get("eventType") or ""))
    canonical = canonical_event_type(event_type) or event_type
    if not event or event != canonical:
        return False
    expected_stage = trigger.get("stage") or trigger.get("stageName") or trigger.get("stage_name")
    if expected_stage and str(expected_stage) != str(stage_name or ""):
        return False
    return bool(trigger.get("workflow_id"))

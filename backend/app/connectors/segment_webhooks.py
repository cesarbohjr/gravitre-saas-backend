"""Segment inbound webhook verification (STA-69)."""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)

SUPPORTED_TRIGGER_EVENTS: tuple[str, ...] = (
    "track",
    "identify",
    "group",
    "page",
    "screen",
)

_EVENT_ALIASES: dict[str, str] = {
    "track": "track",
    "identify": "identify",
    "group": "group",
    "page": "page",
    "screen": "screen",
}


def segment_inbound_webhook_url(settings: Settings, connector_id: str) -> str | None:
    base = (settings.api_public_url or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/api/webhooks/segment/inbound/{connector_id}"


def canonical_event_type(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.strip().lower()
    return _EVENT_ALIASES.get(key, key if key in _EVENT_ALIASES.values() else None)


def verify_segment_webhook_signature(
    *,
    body: bytes,
    signature: str | None,
    secret: str,
) -> bool:
    """Verify Segment webhook HMAC-SHA256 (shared secret)."""
    if not signature or not secret:
        return False
    provided = signature.strip()
    if provided.startswith("sha256="):
        provided = provided[7:]
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


def verify_segment_webhook_secret_header(
    *,
    provided: str | None,
    secret: str,
) -> bool:
    if not provided or not secret:
        return False
    return hmac.compare_digest(provided.strip(), secret.strip())


def normalize_segment_event(event: dict[str, Any]) -> dict[str, Any]:
    """Map inbound Segment payload to workflow parameters."""
    event_type = canonical_event_type(
        str(event.get("type") or event.get("event_type") or event.get("eventType") or "track")
    ) or "track"
    user_id = event.get("userId") or event.get("user_id")
    anonymous_id = event.get("anonymousId") or event.get("anonymous_id")
    track_event = event.get("event") or event.get("name")
    properties = event.get("properties") if isinstance(event.get("properties"), dict) else {}
    traits = event.get("traits") if isinstance(event.get("traits"), dict) else {}
    group_id = event.get("groupId") or event.get("group_id")

    return {
        "segment_event": {
            "type": event_type,
            "userId": user_id,
            "anonymousId": anonymous_id,
            "event": track_event,
            "groupId": group_id,
            "properties": properties,
            "traits": traits,
            "receivedAt": event.get("receivedAt") or event.get("timestamp"),
        },
        "user_id": user_id,
        "anonymous_id": anonymous_id,
        "event_name": track_event,
        "properties": properties,
        "traits": traits,
    }


def event_matches_trigger(trigger: dict[str, Any], *, event_type: str, event_name: str | None = None) -> bool:
    if not trigger.get("active", True):
        return False
    trigger_type = canonical_event_type(str(trigger.get("event_type") or trigger.get("eventType") or "track"))
    canonical = canonical_event_type(event_type) or event_type
    if trigger_type and trigger_type != canonical:
        return False
    expected_name = trigger.get("event_name") or trigger.get("eventName")
    if expected_name and event_name and str(expected_name) != str(event_name):
        return False
    return bool(trigger.get("workflow_id"))


def flatten_inbound_payload(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("batch"), list):
        return [dict(m) for m in payload["batch"] if isinstance(m, dict)]
    return [payload]

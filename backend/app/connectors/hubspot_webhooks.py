"""HubSpot inbound webhooks (STA-16): signature verification and app-level subscriptions."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from typing import Any
from urllib.parse import unquote

import httpx

from app.config import Settings
from app.connectors.hubspot_oauth import hubspot_credentials

logger = logging.getLogger(__name__)

HUBSPOT_WEBHOOKS_API = "https://api.hubapi.com/webhooks/v3"
SIGNATURE_MAX_AGE_MS = 5 * 60 * 1000

V1_SUBSCRIPTION_EVENTS: tuple[tuple[str, str | None], ...] = (
    ("contact.creation", None),
    ("deal.propertyChange", "dealstage"),
)

_HUBSPOT_URI_DECODE = {
    "%3A": ":",
    "%2F": "/",
    "%3F": "?",
    "%40": "@",
    "%21": "!",
    "%24": "$",
    "%27": "'",
    "%28": "(",
    "%29": ")",
    "%2A": "*",
    "%2C": ",",
    "%3B": ";",
}


def hubspot_inbound_webhook_url(settings: Settings) -> str | None:
    base = (settings.api_public_url or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/api/webhooks/hubspot/inbound"


def decode_hubspot_request_uri(uri: str) -> str:
    decoded = uri
    for encoded, plain in _HUBSPOT_URI_DECODE.items():
        decoded = decoded.replace(encoded, plain)
    return unquote(decoded)


def verify_hubspot_signature_v3(
    *,
    method: str,
    request_uri: str,
    body: bytes,
    timestamp_ms: str | None,
    signature: str | None,
    client_secret: str,
) -> bool:
    if not signature or not timestamp_ms or not client_secret:
        return False
    try:
        ts = int(timestamp_ms)
    except ValueError:
        return False
    if abs(int(time.time() * 1000) - ts) > SIGNATURE_MAX_AGE_MS:
        return False

    uri = decode_hubspot_request_uri(request_uri)
    source = f"{method.upper()}{uri}{body.decode('utf-8')}{timestamp_ms}"
    digest = hmac.new(client_secret.encode("utf-8"), source.encode("utf-8"), hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def _developer_request(
    settings: Settings,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any] | list[Any]:
    app_id = (settings.hubspot_app_id or "").strip()
    api_key = (settings.hubspot_developer_api_key or "").strip()
    if not app_id or not api_key:
        raise ValueError("HubSpot app webhooks are not configured (HUBSPOT_APP_ID / HUBSPOT_DEVELOPER_API_KEY)")

    url = f"{HUBSPOT_WEBHOOKS_API}/{app_id}{path}"
    with httpx.Client(timeout=30.0) as client:
        response = client.request(
            method,
            url,
            params={"hapikey": api_key},
            json=json_body,
            headers={"Content-Type": "application/json"},
        )
    if response.status_code >= 400:
        detail = response.text[:500]
        try:
            detail = response.json()
        except Exception:
            pass
        raise RuntimeError(f"HubSpot webhooks API {response.status_code}: {detail}")
    if not response.text:
        return {}
    data = response.json()
    return data if isinstance(data, (dict, list)) else {}


def list_app_subscriptions(settings: Settings) -> list[dict[str, Any]]:
    raw = _developer_request(settings, "GET", "/subscriptions")
    if isinstance(raw, list):
        return [dict(item) for item in raw]
    results = raw.get("results") if isinstance(raw, dict) else None
    if isinstance(results, list):
        return [dict(item) for item in results]
    return []


def ensure_app_webhook_target_url(settings: Settings) -> str | None:
    """Point HubSpot app webhook URL at this API (platform-level). Returns target URL or None."""
    target = hubspot_inbound_webhook_url(settings)
    if not target:
        return None
    try:
        _developer_request(
            settings,
            "PUT",
            "/settings",
            json_body={"targetUrl": target, "throttling": {"maxConcurrentRequests": 10}},
        )
    except ValueError:
        return None
    except RuntimeError as exc:
        logger.warning("hubspot_webhook_settings_update_failed error=%s", exc)
    return target


def ensure_app_event_subscriptions(settings: Settings) -> list[dict[str, Any]]:
    """Ensure v1 event subscriptions exist at app level (all OAuth installs receive events)."""
    if not hubspot_inbound_webhook_url(settings):
        return []
    ensure_app_webhook_target_url(settings)
    existing = list_app_subscriptions(settings)
    existing_keys = {
        (str(item.get("eventType") or ""), item.get("propertyName"))
        for item in existing
        if item.get("active") is not False
    }
    created: list[dict[str, Any]] = []
    for event_type, property_name in V1_SUBSCRIPTION_EVENTS:
        key = (event_type, property_name)
        if key in existing_keys:
            continue
        body: dict[str, Any] = {"eventType": event_type, "active": True}
        if property_name:
            body["propertyName"] = property_name
        try:
            row = _developer_request(settings, "POST", "/subscriptions", json_body=body)
            if isinstance(row, dict):
                created.append(row)
                logger.info("hubspot_subscription_created eventType=%s", event_type)
        except RuntimeError as exc:
            logger.warning("hubspot_subscription_create_failed eventType=%s error=%s", event_type, exc)
    return created


def webhook_client_secret(settings: Settings, *, environment_name: str | None = None) -> str:
    _client_id, secret = hubspot_credentials(settings, environment_name or "production")
    return secret or ""


def normalize_hubspot_event(event: dict[str, Any]) -> dict[str, Any]:
    """Map HubSpot webhook batch item to run parameters."""
    subscription_type = str(event.get("subscriptionType") or event.get("eventType") or "")
    object_id = event.get("objectId")
    portal_id = event.get("portalId")
    property_name = event.get("propertyName")
    property_value = event.get("propertyValue")

    normalized: dict[str, Any] = {
        "hubspot_event": {
            "eventId": event.get("eventId"),
            "subscriptionId": event.get("subscriptionId"),
            "subscriptionType": subscription_type,
            "portalId": portal_id,
            "objectId": object_id,
            "propertyName": property_name,
            "propertyValue": property_value,
            "occurredAt": event.get("occurredAt"),
            "attemptNumber": event.get("attemptNumber"),
        },
    }

    if subscription_type.startswith("contact."):
        normalized["contact"] = {
            "id": str(object_id) if object_id is not None else None,
            "properties": {},
        }
        if property_name:
            normalized["contact"]["properties"][str(property_name)] = property_value
    elif subscription_type.startswith("deal."):
        normalized["deal"] = {
            "id": str(object_id) if object_id is not None else None,
            "properties": {},
        }
        if property_name:
            normalized["deal"]["properties"][str(property_name)] = property_value

    return normalized


def event_matches_trigger(
    trigger: dict[str, Any],
    *,
    subscription_type: str,
    property_name: str | None,
) -> bool:
    if not trigger.get("active", True):
        return False
    event = str(trigger.get("event") or trigger.get("eventType") or "").strip()
    if event != subscription_type:
        return False
    expected_property = trigger.get("property") or trigger.get("propertyName")
    if expected_property and str(expected_property) != str(property_name or ""):
        return False
    return bool(trigger.get("workflow_id"))

"""Thin webhook handlers for Connect Accounts v2 requirement/capability updates."""
from __future__ import annotations

from typing import Any

from stripe import StripeClient

from app.samples.stripe_connect_v2.config import StripeConnectSampleConfig


def parse_thin_notification(
    stripe_client: StripeClient,
    *,
    payload: bytes,
    signature: str | None,
    webhook_secret: str,
) -> Any:
    """Step 7: Parse a *thin* event notification (required for Accounts v2).

    Python SDK equivalent of stripe.parseThinEvent — use parse_event_notification.
    """
    if not signature:
        raise ValueError("Missing Stripe-Signature header")
    return stripe_client.parse_event_notification(payload, signature, webhook_secret)


def handle_thin_event(stripe_client: StripeClient, notification: Any) -> dict[str, Any]:
    """Fetch full v2 event payload and dispatch by type."""
    event_id = getattr(notification, "id", None)
    if not event_id:
        return {"handled": False, "reason": "missing_event_id"}

    # Thin events only contain an id — retrieve the full event for details
    event = stripe_client.v2.core.events.retrieve(str(event_id))
    event_type = str(getattr(event, "type", "") or "")

    if event_type in {"v2.core.account.requirements.updated", "v2.core.account.updated"}:
        if "requirements" in event_type:
            return _handle_requirements_updated(event)
        return _handle_account_updated(event)

    if "capability_status_updated" in event_type:
        return _handle_capability_status_updated(event)

    return {"handled": False, "event_type": event_type}


def _handle_account_updated(event: Any) -> dict[str, Any]:
    return {
        "handled": True,
        "handler": "account_updated",
        "event_type": getattr(event, "type", None),
        "message": "Connected account changed — refresh seller status from API.",
        "data": getattr(event, "data", None),
    }


def _handle_requirements_updated(event: Any) -> dict[str, Any]:
    """v2.account[requirements].updated — seller may need to re-onboard."""
    return {
        "handled": True,
        "handler": "requirements_updated",
        "event_type": getattr(event, "type", None),
        "message": "Connected account requirements changed — prompt seller to complete onboarding.",
        "data": getattr(event, "data", None),
    }


def _handle_capability_status_updated(event: Any) -> dict[str, Any]:
    """v2.account[.recipient].capability_status_updated — transfers may now be active."""
    return {
        "handled": True,
        "handler": "capability_status_updated",
        "event_type": getattr(event, "type", None),
        "message": "Connected account capability status changed — refresh seller status from API.",
        "data": getattr(event, "data", None),
    }


def process_thin_webhook(
    stripe_client: StripeClient,
    config: StripeConnectSampleConfig,
    *,
    payload: bytes,
    signature: str | None,
) -> dict[str, Any]:
    notification = parse_thin_notification(
        stripe_client,
        payload=payload,
        signature=signature,
        webhook_secret=config.stripe_connect_thin_webhook_secret,
    )
    return handle_thin_event(stripe_client, notification)

"""Stripe read helpers behind the governed tool execution layer."""
from __future__ import annotations

from typing import Any

from app.config import Settings
from app.connectors.repository import get_connector_by_type
from app.connectors.stripe_api import get_subscription, resolve_stripe_credentials, subscription_state


def fetch_subscription_state(
    client: Any,
    org_id: str,
    subscription_id: str,
    settings: Settings,
    *,
    environment_name: str | None = "default",
) -> dict[str, Any] | None:
    """Return normalized subscription state for outcome attribution metrics."""
    conn = get_connector_by_type(client, org_id, "stripe", environment_name=environment_name)
    if not conn:
        return None
    api_key, stripe_account = resolve_stripe_credentials(
        client,
        org_id,
        str(conn["id"]),
        settings,
    )
    payload = get_subscription(
        api_key,
        subscription_id,
        stripe_account=stripe_account,
    )
    return subscription_state(payload)

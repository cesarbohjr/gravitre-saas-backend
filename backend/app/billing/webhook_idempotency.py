"""Stripe webhook event idempotency helpers."""
from __future__ import annotations

from typing import Any

from supabase import Client

from app.core.logging import get_logger

logger = get_logger(__name__)

TABLE = "stripe_webhook_events"


def is_webhook_event_processed(client: Client, stripe_event_id: str) -> bool:
    result = (
        client.table(TABLE)
        .select("stripe_event_id")
        .eq("stripe_event_id", stripe_event_id)
        .limit(1)
        .execute()
    )
    return bool(result.data)


def claim_webhook_event(
    client: Client,
    stripe_event_id: str,
    event_type: str,
    org_id: str | None,
) -> bool:
    """Claim an event for processing. Returns False if already claimed/processed."""
    try:
        client.table(TABLE).insert(
            {
                "stripe_event_id": stripe_event_id,
                "event_type": event_type,
                "org_id": org_id,
            }
        ).execute()
        return True
    except Exception as exc:
        if "duplicate key" in str(exc).lower() or "23505" in str(exc):
            return False
        raise


def release_webhook_event_claim(client: Client, stripe_event_id: str) -> None:
    """Remove claim so Stripe retry can re-process after a genuine failure."""
    client.table(TABLE).delete().eq("stripe_event_id", stripe_event_id).execute()


def record_webhook_event_processed(
    client: Client,
    stripe_event_id: str,
    event_type: str,
    org_id: str | None,
) -> None:
    """Record successful processing (no-op if claim row already exists)."""
    if is_webhook_event_processed(client, stripe_event_id):
        return
    client.table(TABLE).insert(
        {
            "stripe_event_id": stripe_event_id,
            "event_type": event_type,
            "org_id": org_id,
        }
    ).execute()

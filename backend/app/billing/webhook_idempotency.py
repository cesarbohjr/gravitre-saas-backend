"""Stripe webhook event idempotency helpers."""
from __future__ import annotations

from typing import Any

from supabase import Client

from app.core.logging import get_logger

logger = get_logger(__name__)

TABLE = "stripe_webhook_events"


def _is_missing_table_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "does not exist" in message
        or "could not find the table" in message
        or "schema cache" in message
        or "pgrst205" in message
    )


def check_webhook_idempotency_table(client: Client) -> dict[str, Any]:
    """Probe whether stripe_webhook_events exists and is readable."""
    try:
        client.table(TABLE).select("stripe_event_id").limit(1).execute()
        return {"table": TABLE, "reachable": True, "error": None}
    except Exception as exc:
        if _is_missing_table_error(exc):
            return {
                "table": TABLE,
                "reachable": False,
                "error": "table_missing",
                "detail": str(exc),
            }
        return {
            "table": TABLE,
            "reachable": False,
            "error": "query_failed",
            "detail": str(exc),
        }


def is_webhook_event_processed(client: Client, stripe_event_id: str) -> bool:
    try:
        result = (
            client.table(TABLE)
            .select("stripe_event_id")
            .eq("stripe_event_id", stripe_event_id)
            .limit(1)
            .execute()
        )
        return bool(result.data)
    except Exception as exc:
        if _is_missing_table_error(exc):
            logger.error(
                "stripe_webhook_events table missing; idempotency disabled until migration is applied"
            )
            return False
        raise


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
        if _is_missing_table_error(exc):
            logger.error(
                "stripe_webhook_events table missing; processing webhook without idempotency claim"
            )
            return True
        raise


def release_webhook_event_claim(client: Client, stripe_event_id: str) -> None:
    """Remove claim so Stripe retry can re-process after a genuine failure."""
    try:
        client.table(TABLE).delete().eq("stripe_event_id", stripe_event_id).execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            logger.warning("stripe_webhook_events table missing; skip releasing claim for %s", stripe_event_id)
            return
        raise


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

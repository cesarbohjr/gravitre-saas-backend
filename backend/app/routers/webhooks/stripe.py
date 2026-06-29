from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from supabase import create_client

from app.billing.service import resolve_org_id_from_checkout_metadata
from app.billing.stripe import verify_webhook
from app.billing.webhook_idempotency import (
    claim_webhook_event,
    is_webhook_event_processed,
    release_webhook_event_claim,
)
from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _to_iso(ts: int | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _normalize_tier(raw_tier: str | None) -> str:
    value = (raw_tier or "free").strip().lower()
    if value in {"starter"}:
        return "node"
    if value in {"growth"}:
        return "control"
    if value in {"scale", "enterprise"}:
        return "command"
    if value in {"node", "control", "command", "free"}:
        return value
    return "free"


def _plan_from_price(settings: Settings, price_id: str | None) -> str:
    if not price_id:
        return "free"
    price_to_plan = {
        settings.stripe_price_id_node_monthly: "node",
        settings.stripe_price_id_node_annual: "node",
        settings.stripe_price_id_control_monthly: "control",
        settings.stripe_price_id_control_annual: "control",
        settings.stripe_price_id_command_monthly: "command",
        settings.stripe_price_id_command_annual: "command",
        settings.stripe_price_id_starter: "node",
        settings.stripe_price_id_growth: "control",
        settings.stripe_price_id_scale: "command",
    }
    plan = price_to_plan.get(price_id)
    return _normalize_tier(plan)


def _write_event(client, org_id: str | None, event_type: str, payload: dict[str, Any], status_value: str = "success") -> None:
    if not org_id:
        return
    client.table("billing_events").insert(
        {
            "org_id": org_id,
            "action": event_type,
            "event_type": event_type,
            "status": status_value,
            "payload": payload,
        }
    ).execute()


def _upsert_subscription_from_event(client, settings: Settings, org_id: str | None, data: dict[str, Any]) -> None:
    if not org_id:
        return
    items = (data.get("items") or {}).get("data") or []
    primary_item = items[0] if items else {}
    price_id = (primary_item.get("price") or {}).get("id")
    quantity = int(primary_item.get("quantity") or data.get("quantity") or 1)
    plan_tier = _plan_from_price(settings, price_id)
    payload = {
        "org_id": org_id,
        "stripe_customer_id": data.get("customer"),
        "stripe_subscription_id": data.get("id"),
        "tier": plan_tier,
        "status": data.get("status") or "active",
        "current_period_start": _to_iso(data.get("current_period_start")),
        "current_period_end": _to_iso(data.get("current_period_end")),
        "seat_count": quantity,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    client.table("subscriptions").upsert(payload, on_conflict="org_id").execute()


def _process_stripe_event(
    client,
    settings: Settings,
    event_type: str,
    data: dict[str, Any],
    metadata: dict[str, Any],
    org_id: str | None,
    event: dict[str, Any],
) -> None:
    if not org_id:
        org_id = resolve_org_id_from_checkout_metadata(client, metadata)

    if event_type == "checkout.session.completed":
        from app.marketplace.entitlements import fulfill_entitlement_from_checkout

        marketplace_entitlement = fulfill_entitlement_from_checkout(client, settings, session=data)
        if marketplace_entitlement:
            _write_event(
                client,
                org_id,
                "marketplace.checkout.completed",
                {"entitlement": marketplace_entitlement, "sessionId": data.get("id")},
            )
        subscription_id = data.get("subscription")
        customer_id = data.get("customer")
        if org_id and subscription_id:
            client.table("subscriptions").upsert(
                {
                    "org_id": org_id,
                    "stripe_customer_id": customer_id,
                    "stripe_subscription_id": subscription_id,
                    "status": "active",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="org_id",
            ).execute()
            client.table("org_billing").upsert(
                {
                    "org_id": org_id,
                    "stripe_customer_id": customer_id,
                    "stripe_subscription_id": subscription_id,
                    "billing_status": "active",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="org_id",
            ).execute()

    if event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        _upsert_subscription_from_event(client, settings, org_id, data)
        if org_id:
            items = (data.get("items") or {}).get("data") or []
            primary_item = items[0] if items else {}
            price_id = (primary_item.get("price") or {}).get("id")
            plan_code = (metadata.get("plan_code") if isinstance(metadata, dict) else None) or _plan_from_price(
                settings, price_id
            )
            billing_status = data.get("status") or "active"
            if billing_status == "incomplete":
                billing_status = "pending"
            client.table("org_billing").upsert(
                {
                    "org_id": org_id,
                    "stripe_customer_id": data.get("customer"),
                    "stripe_subscription_id": data.get("id"),
                    "plan_code": plan_code,
                    "billing_status": billing_status,
                    "current_period_end": _to_iso(data.get("current_period_end")),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="org_id",
            ).execute()

    if event_type == "customer.subscription.deleted":
        subscription_id = data.get("id")
        if subscription_id:
            client.table("subscriptions").update(
                {
                    "status": "canceled",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("stripe_subscription_id", subscription_id).execute()
            client.table("org_billing").update(
                {
                    "billing_status": "cancelled",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("stripe_subscription_id", subscription_id).execute()

    if event_type == "invoice.payment_succeeded":
        if org_id:
            client.table("subscriptions").update(
                {"status": "active", "updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("org_id", org_id).execute()

    if event_type == "invoice.payment_failed":
        if org_id:
            client.table("subscriptions").update(
                {"status": "past_due", "updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("org_id", org_id).execute()

    _write_event(client, org_id, event_type, event)


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook secret is not configured",
        )

    payload_bytes = await request.body()
    signature = request.headers.get("stripe-signature")
    event = verify_webhook(settings, payload_bytes, signature)

    stripe_event_id = str(getattr(event, "id", None) or event.get("id") or "")
    event_type = str(getattr(event, "type", None) or event.get("type") or "")
    data = event.get("data", {}).get("object", {}) or {}
    metadata = data.get("metadata") or {}
    org_id = metadata.get("org_id")

    if not stripe_event_id:
        raise HTTPException(status_code=400, detail="Stripe event id missing")

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    if is_webhook_event_processed(client, stripe_event_id):
        logger.info("Skipping duplicate Stripe webhook event %s", stripe_event_id)
        return {"status": "already_processed", "received": True}

    if not claim_webhook_event(client, stripe_event_id, event_type, org_id):
        logger.info("Skipping duplicate Stripe webhook event %s (concurrent claim)", stripe_event_id)
        return {"status": "already_processed", "received": True}

    try:
        _process_stripe_event(client, settings, event_type, data, metadata, org_id, event)
    except Exception:
        release_webhook_event_claim(client, stripe_event_id)
        raise

    return {"received": True}

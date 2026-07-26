from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from supabase import create_client

from app.billing.service import (
    resolve_org_id_from_checkout_metadata,
    resolve_org_id_from_stripe_customer,
)
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

# subscriptions.status CHECK allows only these values (see monetization migration).
_ALLOWED_SUBSCRIPTION_STATUSES = frozenset({"active", "past_due", "canceled", "trialing", "inactive"})
_STRIPE_SUBSCRIPTION_STATUS_MAP = {
    "active": "active",
    "trialing": "trialing",
    "past_due": "past_due",
    "canceled": "canceled",
    "cancelled": "canceled",
    "incomplete": "inactive",
    "incomplete_expired": "inactive",
    "unpaid": "past_due",
    "paused": "inactive",
}
_VALID_BILLING_PLAN_CODES = frozenset({"node", "control", "command", "enterprise"})


def _to_iso(ts: int | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _sanitize_org_id(org_id: str | None) -> str | None:
    value = str(org_id or "").strip()
    return value or None


def _normalize_subscription_status(stripe_status: str | None) -> str:
    """Map Stripe subscription.status to subscriptions.status CHECK values."""
    normalized = str(stripe_status or "active").strip().lower()
    mapped = _STRIPE_SUBSCRIPTION_STATUS_MAP.get(normalized, normalized)
    if mapped in _ALLOWED_SUBSCRIPTION_STATUSES:
        return mapped
    logger.warning("Unknown Stripe subscription status %r; storing as inactive", stripe_status)
    return "inactive"


def _normalize_billing_plan_code(plan_code: str | None) -> str | None:
    """Return a billing_plans FK-safe code, or None when unknown."""
    normalized = _normalize_tier(plan_code)
    if normalized in _VALID_BILLING_PLAN_CODES:
        return normalized
    return None


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


def _plan_from_price(settings: Settings, price_id: str | None) -> str | None:
    """Map a Stripe price id to a plan code. None when unknown (do not invent free/node)."""
    if not price_id:
        return None
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
    # Ignore blank env mappings so "" keys cannot collide and swallow real price ids.
    cleaned = {str(k): v for k, v in price_to_plan.items() if str(k or "").strip()}
    plan = cleaned.get(price_id)
    if not plan:
        return None
    return _normalize_tier(plan)


def _plan_from_subscription_items(settings: Settings, data: dict[str, Any]) -> str | None:
    """Pick the first known *base* plan price from subscription items (skip metered)."""
    items = (data.get("items") or {}).get("data") or []
    for item in items:
        price = item.get("price") if isinstance(item, dict) else None
        price_id = (price or {}).get("id") if isinstance(price, dict) else None
        if isinstance(price, dict):
            recurring = price.get("recurring") if isinstance(price.get("recurring"), dict) else {}
            if str(recurring.get("usage_type") or "").lower() == "metered":
                continue
        mapped = _plan_from_price(settings, price_id)
        if mapped and mapped != "free":
            return mapped
    return None


def _resolve_plan_code(
    settings: Settings,
    data: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> str | None:
    meta = metadata if isinstance(metadata, dict) else {}
    from_meta = _normalize_billing_plan_code(meta.get("plan_code") if meta else None)
    if from_meta:
        return from_meta
    from_items = _plan_from_subscription_items(settings, data)
    if from_items:
        return _normalize_billing_plan_code(from_items)
    return None


def _stripe_event_dict(event: Any) -> dict[str, Any]:
    if hasattr(event, "to_dict"):
        return event.to_dict()
    if isinstance(event, dict):
        return event
    return dict(event)


def _resolve_org_id(client, data: dict[str, Any], metadata: dict[str, Any]) -> str | None:
    org_id = str(metadata.get("org_id") or "").strip() or None
    if org_id:
        return org_id
    org_id = resolve_org_id_from_checkout_metadata(client, metadata)
    if org_id:
        return org_id
    return resolve_org_id_from_stripe_customer(client, data.get("customer"))


def _write_event(client, org_id: str | None, event_type: str, payload: Any, status_value: str = "success") -> None:
    if not org_id:
        return
    client.table("billing_events").insert(
        {
            "org_id": org_id,
            "action": event_type,
            "event_type": event_type,
            "status": status_value,
            "payload": _stripe_event_dict(payload),
        }
    ).execute()


def _upsert_subscription_from_event(
    client,
    settings: Settings,
    org_id: str | None,
    data: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> None:
    if not org_id:
        return
    items = (data.get("items") or {}).get("data") or []
    primary_item = items[0] if items else {}
    quantity = int(primary_item.get("quantity") or data.get("quantity") or 1)
    meta = metadata if isinstance(metadata, dict) else (data.get("metadata") if isinstance(data.get("metadata"), dict) else {})
    plan_tier = _resolve_plan_code(settings, data, meta) or "free"
    payload = {
        "org_id": org_id,
        "stripe_customer_id": data.get("customer"),
        "stripe_subscription_id": data.get("id"),
        "tier": plan_tier,
        "status": _normalize_subscription_status(data.get("status")),
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
    event: Any,
) -> None:
    org_id = org_id or _resolve_org_id(client, data, metadata)

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
            from app.services.org_membership import (
                promote_user_to_org_owner,
                resolve_user_id_by_email,
            )

            payer_user_id = str(
                metadata.get("user_id")
                or data.get("client_reference_id")
                or ""
            ).strip()
            if not payer_user_id:
                details = data.get("customer_details") if isinstance(data.get("customer_details"), dict) else {}
                checkout_email = (
                    str(details.get("email") or "").strip()
                    or str(data.get("customer_email") or "").strip()
                    or str(metadata.get("checkout_email") or "").strip()
                )
                payer_user_id = resolve_user_id_by_email(client, checkout_email) or ""
            if payer_user_id:
                promote_user_to_org_owner(client, org_id, payer_user_id)
            plan_code = _normalize_billing_plan_code(
                (metadata.get("plan_code") if isinstance(metadata, dict) else None)
            )
            subscription_row: dict[str, Any] = {
                "org_id": org_id,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "status": "active",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            org_billing_row: dict[str, Any] = {
                "org_id": org_id,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "billing_status": "active",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if plan_code:
                subscription_row["tier"] = plan_code
                org_billing_row["plan_code"] = plan_code
            client.table("subscriptions").upsert(subscription_row, on_conflict="org_id").execute()
            client.table("org_billing").upsert(org_billing_row, on_conflict="org_id").execute()

    if event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        _upsert_subscription_from_event(client, settings, org_id, data, metadata)
        if org_id and event_type == "customer.subscription.created":
            from app.services.org_membership import (
                promote_user_to_org_owner,
                resolve_user_id_by_email,
            )

            payer_user_id = str(metadata.get("user_id") or "").strip()
            if not payer_user_id:
                payer_user_id = resolve_user_id_by_email(
                    client, str(metadata.get("checkout_email") or "").strip()
                ) or ""
            if payer_user_id:
                promote_user_to_org_owner(client, org_id, payer_user_id)
        if org_id:
            plan_code = _resolve_plan_code(settings, data, metadata if isinstance(metadata, dict) else {})
            billing_status = data.get("status") or "active"
            if billing_status == "incomplete":
                billing_status = "pending"
            org_billing_row = {
                "org_id": org_id,
                "stripe_customer_id": data.get("customer"),
                "stripe_subscription_id": data.get("id"),
                "billing_status": billing_status,
                "current_period_end": _to_iso(data.get("current_period_end")),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if plan_code:
                org_billing_row["plan_code"] = plan_code
            client.table("org_billing").upsert(org_billing_row, on_conflict="org_id").execute()

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

    if event_type == "account.updated":
        from app.services.marketplace_billing_service import handle_connect_account_updated

        handle_connect_account_updated(client, settings, data if isinstance(data, dict) else {})

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
    try:
        event = verify_webhook(settings, payload_bytes, signature)
    except stripe.error.SignatureVerificationError as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature") from exc
    except ValueError as exc:
        logger.warning("Stripe webhook payload invalid: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook payload") from exc

    stripe_event_id = str(getattr(event, "id", None) or event.get("id") or "")
    event_type = str(getattr(event, "type", None) or event.get("type") or "")
    data = event.get("data", {}).get("object", {}) or {}
    metadata = data.get("metadata") or {}
    org_id = _sanitize_org_id(metadata.get("org_id"))

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
        logger.exception("Stripe webhook processing failed for event %s (%s)", stripe_event_id, event_type)
        raise

    return {"received": True}

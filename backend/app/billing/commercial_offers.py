"""Founder-controlled commercial segmentation and checkout offer resolution.

Identity category and temporary promotion are deliberately separate dimensions.
Only the service-role backend reads these tables; unreviewed is not a customer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utc_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def checkout_offer_for_org(client: Any, org_id: str, *, now: datetime | None = None) -> dict[str, Any] | None:
    """Return only an available, unexpired founder-issued grant.

    Missing/malformed data fails closed. Checkout cannot accept a client-supplied
    trial length or coupon ID.
    """
    rows = (
        client.table("org_promotional_grants")
        .select("id,offer_type,trial_days,stripe_coupon_id,status,valid_until")
        .eq("org_id", org_id)
        .eq("status", "available")
        .limit(2)
        .execute()
        .data or []
    )
    if len(rows) != 1:
        return None
    grant = rows[0]
    expires = _utc_datetime(grant.get("valid_until"))
    if grant.get("valid_until") and not expires:
        return None
    if expires and expires <= (now or datetime.now(timezone.utc)):
        return None
    if grant.get("offer_type") == "trial":
        days = grant.get("trial_days")
        if not isinstance(days, int) or not 1 <= days <= 90:
            return None
        return {"grant_id": str(grant["id"]), "trial_days": days}
    if grant.get("offer_type") == "discount":
        coupon = grant.get("stripe_coupon_id")
        if not isinstance(coupon, str) or not coupon.strip():
            return None
        return {"grant_id": str(grant["id"]), "stripe_coupon_id": coupon.strip()}
    return None


def redeem_checkout_offer(client: Any, org_id: str, grant_id: str, subscription_id: str) -> bool:
    """Mark a trusted Stripe Checkout offer as redeemed, idempotently.

    Only a signed checkout.session.completed webhook invokes this function.
    The conditional update prevents reuse after a successful checkout.
    """
    from uuid import UUID
    try:
        grant_id = str(UUID(str(grant_id)))
    except (TypeError, ValueError):
        return False
    if not org_id or not subscription_id:
        return False
    response = (
        client.table("org_promotional_grants")
        .update({
            "status": "redeemed",
            "redeemed_at": datetime.now(timezone.utc).isoformat(),
            "stripe_subscription_id": subscription_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", grant_id)
        .eq("org_id", org_id)
        .eq("status", "available")
        .execute()
    )
    return bool(response.data)


def segment_for_org(client: Any, org_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Four reporting cohorts, with unreviewed excluded from customer KPIs.

    'promotional' is an acquisition cohort, not a subscription payment status.
    Stripe remains authoritative for paid/trialing subscription and revenue.
    """
    rows = (
        client.table("org_commercial_profiles")
        .select("customer_category,classification_reason")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data or []
    )
    category = rows[0].get("customer_category", "unreviewed") if rows else "unreviewed"
    grant = checkout_offer_for_org(client, org_id, now=now)
    if not grant:
        history = (
            client.table("org_promotional_grants")
            .select("id,status")
            .eq("org_id", org_id)
            .eq("status", "redeemed")
            .limit(1)
            .execute()
            .data or []
        )
        has_promo = bool(history)
    else:
        has_promo = True
    return {
        "customer_category": category,
        "reporting_segment": (
            "promotional" if category == "external" and has_promo else category
        ),
        "promotional_offer": grant,
    }

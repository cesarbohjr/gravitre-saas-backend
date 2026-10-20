"""Founder-offer operations: customer-safe offer read, stuck checkout release,
and Stripe coupon cleanup on revoke."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import stripe
from fastapi import HTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


def founder_offer_summary(grant: dict[str, Any]) -> str:
    if grant.get("offer_type") == "trial":
        return f"a {int(grant.get('trial_days') or 0)}-day free trial"
    pct = float(grant.get("percent_off") or 0)
    months = int(grant.get("discount_months") or 0)
    return f"{pct:g}% off for {months} month{'s' if months != 1 else ''}"


def customer_founder_offer(client: Any, settings: Any, org_id: str) -> dict[str, Any] | None:
    """The org's own available founder offer, without internal identifiers."""
    if not getattr(settings, "commercial_offers_enabled", False):
        return None
    from app.billing.commercial_offers import checkout_offer_for_org

    offer = checkout_offer_for_org(client, org_id)
    if not offer:
        return None
    rows = (
        client.table("org_promotional_grants")
        .select("offer_type,trial_days,percent_off,discount_months,valid_until,checkout_attempt_id")
        .eq("id", offer["grant_id"])
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return None
    grant = rows[0]
    summary = founder_offer_summary(grant)
    return {
        "offer_type": grant.get("offer_type"),
        "trial_days": grant.get("trial_days"),
        "percent_off": float(grant["percent_off"]) if grant.get("percent_off") is not None else None,
        "discount_months": grant.get("discount_months"),
        "valid_until": grant.get("valid_until"),
        "checkout_in_progress": bool(grant.get("checkout_attempt_id")),
        "summary": summary,
        "message": f"You have {summary} on any paid plan. It's applied automatically at checkout.",
    }


def delete_coupon_best_effort(settings: Any, coupon_id: str | None) -> bool:
    """Delete a founder coupon in Stripe. Existing subscriptions keep their
    discount; deletion only prevents any future application. Logged, never raises."""
    if not coupon_id or not getattr(settings, "stripe_secret_key", ""):
        return False
    from app.billing.stripe import init_stripe

    init_stripe(settings)
    try:
        stripe.Coupon.delete(coupon_id)
        return True
    except stripe.error.InvalidRequestError as exc:
        if "no such coupon" in str(exc).lower():
            return True
        logger.warning("founder_coupon_delete_failed coupon=%s err=%s", coupon_id, type(exc).__name__)
    except stripe.error.StripeError as exc:
        logger.warning("founder_coupon_delete_failed coupon=%s err=%s", coupon_id, type(exc).__name__)
    return False


def release_reserved_checkout(client: Any, settings: Any, grant_id: str) -> dict[str, Any]:
    """Clear a stuck "Checkout reserved" founder grant after verifying Stripe.

    Fails closed: if a Checkout session for the attempt completed, or a live
    subscription carries the attempt, the grant was (or is being) redeemed and
    is not released. Open sessions are expired first so the old link cannot be
    paid after release.
    """
    rows = (
        client.table("org_promotional_grants")
        .select("id,org_id,status,checkout_attempt_id,checkout_customer_id")
        .eq("id", grant_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Offer not found")
    grant = rows[0]
    attempt = grant.get("checkout_attempt_id")
    if grant.get("status") != "available" or not attempt:
        raise HTTPException(status_code=409, detail="Only an available offer with a reserved checkout can be released")
    customer_id = grant.get("checkout_customer_id")
    expired_sessions: list[str] = []
    if customer_id:
        if not getattr(settings, "stripe_secret_key", ""):
            raise HTTPException(status_code=503, detail="Stripe is not configured; cannot verify the reserved checkout")
        from app.billing.stripe import init_stripe

        init_stripe(settings)
        try:
            sessions = stripe.checkout.Session.list(customer=customer_id, limit=100)
            for session in sessions.get("data", []):
                if str((session.get("metadata") or {}).get("offer_attempt_id") or "") != str(attempt):
                    continue
                if session.get("status") == "complete":
                    raise HTTPException(
                        status_code=409,
                        detail="The reserved checkout completed in Stripe; wait for the webhook or reconcile instead of releasing",
                    )
                if session.get("status") == "open":
                    stripe.checkout.Session.expire(session["id"])
                    expired_sessions.append(session["id"])
            subscriptions = stripe.Subscription.list(customer=customer_id, status="all", limit=100)
            for sub in subscriptions.get("data", []):
                if str((sub.get("metadata") or {}).get("offer_attempt_id") or "") == str(attempt) and sub.get(
                    "status"
                ) not in {"canceled", "incomplete_expired"}:
                    raise HTTPException(
                        status_code=409,
                        detail="A Stripe subscription already uses this offer; reconcile instead of releasing",
                    )
        except stripe.error.StripeError as exc:
            raise HTTPException(
                status_code=502, detail="Could not verify the reserved checkout in Stripe; nothing was released"
            ) from exc
    updated = (
        client.table("org_promotional_grants")
        .update(
            {
                "checkout_attempt_id": None,
                "checkout_reserved_at": None,
                "checkout_customer_id": None,
                "checkout_price_id": None,
                "checkout_user_id": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", grant_id)
        .eq("status", "available")
        .eq("checkout_attempt_id", attempt)
        .execute()
        .data
    )
    if not updated:
        raise HTTPException(status_code=409, detail="The offer changed concurrently; refresh and review it")
    return {
        "grant_id": grant_id,
        "org_id": grant["org_id"],
        "released_attempt_id": str(attempt),
        "expired_checkout_sessions": expired_sessions,
    }

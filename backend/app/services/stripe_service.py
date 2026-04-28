from __future__ import annotations

from typing import Any

import stripe

from app.config import Settings


def _init_stripe(settings: Settings) -> None:
    if not settings.stripe_secret_key:
        raise ValueError("stripe_secret_key is not configured")
    stripe.api_key = settings.stripe_secret_key


def create_customer(org_id: str, email: str | None, settings: Settings) -> dict[str, Any]:
    _init_stripe(settings)
    customer = stripe.Customer.create(
        email=email or None,
        metadata={"org_id": org_id},
    )
    return dict(customer)


def create_subscription(
    customer_id: str,
    price_id: str,
    quantity: int,
    settings: Settings,
) -> dict[str, Any]:
    _init_stripe(settings)
    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": price_id, "quantity": max(quantity, 1)}],
        payment_behavior="default_incomplete",
        payment_settings={"save_default_payment_method": "on_subscription"},
        expand=["latest_invoice.payment_intent"],
    )
    return dict(subscription)


def update_subscription(
    subscription_id: str,
    new_price_id: str,
    quantity: int,
    settings: Settings,
) -> dict[str, Any]:
    _init_stripe(settings)
    existing = stripe.Subscription.retrieve(subscription_id)
    items = existing.get("items", {}).get("data", [])
    if not items:
        raise ValueError("Subscription has no items to update")
    item_id = items[0]["id"]
    updated = stripe.Subscription.modify(
        subscription_id,
        items=[{"id": item_id, "price": new_price_id, "quantity": max(quantity, 1)}],
        proration_behavior="create_prorations",
    )
    return dict(updated)


def cancel_subscription(
    subscription_id: str,
    immediate: bool,
    settings: Settings,
) -> dict[str, Any]:
    _init_stripe(settings)
    if immediate:
        canceled = stripe.Subscription.cancel(subscription_id)
    else:
        canceled = stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
    return dict(canceled)


def get_customer_portal_url(customer_id: str, return_url: str, settings: Settings) -> str:
    _init_stripe(settings)
    session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
    return str(session.url)


def add_addon_to_subscription(
    subscription_id: str,
    addon_price_id: str,
    quantity: int,
    settings: Settings,
) -> dict[str, Any]:
    _init_stripe(settings)
    stripe.SubscriptionItem.create(
        subscription=subscription_id,
        price=addon_price_id,
        quantity=max(quantity, 1),
        proration_behavior="create_prorations",
    )
    refreshed = stripe.Subscription.retrieve(subscription_id)
    return dict(refreshed)

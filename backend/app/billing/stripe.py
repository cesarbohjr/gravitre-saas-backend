from __future__ import annotations

from typing import Any

import stripe

from app.config import Settings


def init_stripe(settings: Settings) -> None:
    stripe.api_key = settings.stripe_secret_key


def price_id_for_plan(settings: Settings, plan_code: str) -> str | None:
    mapping = {
        "starter": settings.stripe_price_id_starter,
        "growth": settings.stripe_price_id_growth,
        "scale": settings.stripe_price_id_scale,
    }
    return mapping.get(plan_code)


def plan_code_for_price(settings: Settings, price_id: str | None) -> str | None:
    if not price_id:
        return None
    if price_id == settings.stripe_price_id_starter:
        return "starter"
    if price_id == settings.stripe_price_id_growth:
        return "growth"
    if price_id == settings.stripe_price_id_scale:
        return "scale"
    return None


def create_checkout_session(
    settings: Settings,
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    metadata: dict[str, Any],
) -> stripe.checkout.Session:
    init_stripe(settings)
    return stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )


def create_customer_portal(settings: Settings, customer_id: str, return_url: str) -> stripe.billing_portal.Session:
    init_stripe(settings)
    return stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)


def verify_webhook(settings: Settings, payload: bytes, signature: str | None) -> stripe.Event:
    init_stripe(settings)
    return stripe.Webhook.construct_event(
        payload=payload,
        sig_header=signature or "",
        secret=settings.stripe_webhook_secret,
    )

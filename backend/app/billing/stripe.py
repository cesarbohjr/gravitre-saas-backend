from __future__ import annotations

from typing import Any

import stripe

from app.config import Settings


def init_stripe(settings: Settings) -> None:
    stripe.api_key = settings.stripe_secret_key


def _normalize_plan_code(plan_code: str | None) -> str | None:
    code = (plan_code or "").strip().lower()
    if not code:
        return None
    if code == "starter":
        return "node"
    if code == "growth":
        return "control"
    if code in {"scale", "enterprise"}:
        return "command"
    if code in {"node", "control", "command", "free"}:
        return code
    return code


def _normalize_billing_interval(billing_interval: str | None) -> str:
    value = (billing_interval or "").strip().lower()
    if value in {"annual", "year", "yearly"}:
        return "annual"
    return "monthly"


def price_id_for_plan(settings: Settings, plan_code: str, billing_interval: str | None = None) -> str | None:
    normalized_plan = _normalize_plan_code(plan_code)
    if not normalized_plan:
        return None

    interval = _normalize_billing_interval(billing_interval)
    if normalized_plan == "node":
        if interval == "annual":
            return settings.stripe_price_id_node_annual or settings.stripe_price_id_starter
        return settings.stripe_price_id_node_monthly or settings.stripe_price_id_starter
    if normalized_plan == "control":
        if interval == "annual":
            return settings.stripe_price_id_control_annual or settings.stripe_price_id_growth
        return settings.stripe_price_id_control_monthly or settings.stripe_price_id_growth
    if normalized_plan == "command":
        if interval == "annual":
            return settings.stripe_price_id_command_annual or settings.stripe_price_id_scale
        return settings.stripe_price_id_command_monthly or settings.stripe_price_id_scale
    return None


def plan_code_for_price(settings: Settings, price_id: str | None) -> str | None:
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
    mapped = price_to_plan.get(price_id)
    if mapped:
        return mapped
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

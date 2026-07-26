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


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


def price_id_for_plan(settings: Settings, plan_code: str, billing_interval: str | None = None) -> str | None:
    normalized_plan = _normalize_plan_code(plan_code)
    if not normalized_plan:
        return None

    interval = _normalize_billing_interval(billing_interval)
    if normalized_plan == "node":
        if interval == "annual":
            return _first_non_empty(
                settings.stripe_price_id_node_annual,
                settings.stripe_price_id_node_monthly,
                settings.stripe_price_id_starter,
            )
        return _first_non_empty(settings.stripe_price_id_node_monthly, settings.stripe_price_id_starter)
    if normalized_plan == "control":
        if interval == "annual":
            return _first_non_empty(
                settings.stripe_price_id_control_annual,
                settings.stripe_price_id_control_monthly,
                settings.stripe_price_id_growth,
            )
        return _first_non_empty(settings.stripe_price_id_control_monthly, settings.stripe_price_id_growth)
    if normalized_plan == "command":
        if interval == "annual":
            return _first_non_empty(
                settings.stripe_price_id_command_annual,
                settings.stripe_price_id_command_monthly,
                settings.stripe_price_id_scale,
            )
        return _first_non_empty(settings.stripe_price_id_command_monthly, settings.stripe_price_id_scale)
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


def metered_price_id_for_plan(settings: Settings, plan_code: str | None) -> str | None:
    """Per-plan usage-based (metered) price id, if configured. Empty -> None."""
    code = _normalize_plan_code(plan_code)
    mapping = {
        "node": settings.stripe_metered_price_id_node,
        "control": settings.stripe_metered_price_id_control,
        "command": settings.stripe_metered_price_id_command,
    }
    return (mapping.get(code or "") or "").strip() or None


def research_lookup_metered_price_for_subscription(settings: Settings) -> str | None:
    """Global metered price for research lookup overage (same price all tiers)."""
    from app.billing.stripe_research_lookup_metering import research_lookup_metered_price_id

    return research_lookup_metered_price_id(settings) or None


def _subscription_line_items(
    settings: Settings,
    price_id: str,
    quantity: int = 1,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = [{"price": price_id, "quantity": max(quantity, 1)}]
    attached_prices = {price_id}
    metered = metered_price_id_for_plan(settings, plan_code_for_price(settings, price_id))
    if metered and metered not in attached_prices:
        items.append({"price": metered})
        attached_prices.add(metered)
    research_metered = research_lookup_metered_price_for_subscription(settings)
    if research_metered and research_metered not in attached_prices:
        items.append({"price": research_metered})
    return items


def _payment_intent_client_secret(payment_intent: Any) -> str | None:
    """Resolve a PaymentIntent client_secret from an object or an id (pre-Basil API)."""
    if isinstance(payment_intent, dict):
        return payment_intent.get("client_secret")
    if isinstance(payment_intent, str) and payment_intent:
        try:
            return stripe.PaymentIntent.retrieve(payment_intent).get("client_secret")
        except stripe.error.StripeError:
            return None
    return None


def _invoice_client_secret(latest_invoice: Any) -> str | None:
    """Extract the Payment Element client_secret from a subscription's latest invoice.

    Stripe's Basil API release (2025-03-31) removed ``Invoice.payment_intent`` and
    exposes the secret via ``invoice.confirmation_secret`` instead. Older API
    versions still use ``invoice.payment_intent``. This handles both, and falls
    back to retrieving the invoice/PaymentIntent by id when the field was not
    expanded — without ever creating a second subscription.
    """
    if not latest_invoice:
        return None

    invoice_id: str | None = None
    if isinstance(latest_invoice, dict):
        invoice_id = latest_invoice.get("id")
        # Basil+: confirmation_secret carries the client_secret.
        confirmation_secret = latest_invoice.get("confirmation_secret") or {}
        client_secret = confirmation_secret.get("client_secret")
        if client_secret:
            return client_secret
        # Pre-Basil: payment_intent (object or id).
        client_secret = _payment_intent_client_secret(latest_invoice.get("payment_intent"))
        if client_secret:
            return client_secret
    elif isinstance(latest_invoice, str):
        invoice_id = latest_invoice

    if not invoice_id:
        return None

    # The secret was not present on the expanded object — retrieve it explicitly.
    try:
        invoice = stripe.Invoice.retrieve(invoice_id, expand=["confirmation_secret"])
        confirmation_secret = invoice.get("confirmation_secret") or {}
        client_secret = confirmation_secret.get("client_secret")
        if client_secret:
            return client_secret
        return _payment_intent_client_secret(invoice.get("payment_intent"))
    except stripe.error.InvalidRequestError:
        # confirmation_secret is not a valid expand on this (older) API version.
        try:
            invoice = stripe.Invoice.retrieve(invoice_id, expand=["payment_intent"])
            return _payment_intent_client_secret(invoice.get("payment_intent"))
        except stripe.error.StripeError:
            return None
    except stripe.error.StripeError:
        return None


def create_subscription_for_payment_element(
    settings: Settings,
    customer_id: str,
    price_id: str,
    metadata: dict[str, Any],
    quantity: int = 1,
) -> dict[str, Any]:
    """Create an incomplete subscription and return Payment Element client_secret."""
    init_stripe(settings)
    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=_subscription_line_items(settings, price_id, quantity),
        metadata=metadata,
        payment_behavior="default_incomplete",
        payment_settings={"save_default_payment_method": "on_subscription"},
        # Basil API (2025-03-31+) exposes the secret via confirmation_secret;
        # _invoice_client_secret() falls back to payment_intent for older versions.
        expand=["latest_invoice.confirmation_secret"],
    )
    client_secret = _invoice_client_secret(subscription.get("latest_invoice"))
    if not client_secret:
        raise ValueError("Stripe subscription missing payment client_secret")
    return {
        "subscription_id": subscription.get("id"),
        "customer_id": customer_id,
        "client_secret": client_secret,
        "subscription_status": subscription.get("status"),
    }


def create_checkout_session(
    settings: Settings,
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    metadata: dict[str, Any],
) -> stripe.checkout.Session:
    init_stripe(settings)
    line_items = _subscription_line_items(settings, price_id, quantity=1)
    return stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=line_items,
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

from __future__ import annotations

from typing import Any

import stripe

from app.config import Settings

# Pre–2026-08 voice-included list prices. Existing subscriptions keep these
# Price objects indefinitely; checkout env vars point at the new Prices.
LEGACY_STRIPE_PLAN_PRICE_IDS: dict[str, str] = {
    "price_1TbcngGkcGZTLqrPy3N5B60J": "node",  # $49/mo
    "price_1TbcnhGkcGZTLqrPienI3Lyl": "node",  # $492/yr
    "price_1TbcnhGkcGZTLqrP0jEnqsWk": "control",  # $129/mo
    "price_1TbcnhGkcGZTLqrPklUxFvRc": "control",  # $1284/yr
    "price_1TbcniGkcGZTLqrPGRwaFxgZ": "command",  # $299/mo
    "price_1TbcniGkcGZTLqrPhzsyjkTj": "command",  # $2988/yr
}

# unit_amount cents + interval for every known platform plan Price (legacy + current).
STRIPE_PLAN_PRICE_AMOUNTS: dict[str, dict[str, Any]] = {
    # Legacy (grandfathered)
    "price_1TbcngGkcGZTLqrPy3N5B60J": {"plan": "node", "unit_amount": 4900, "interval": "month"},
    "price_1TbcnhGkcGZTLqrPienI3Lyl": {"plan": "node", "unit_amount": 49200, "interval": "year"},
    "price_1TbcnhGkcGZTLqrP0jEnqsWk": {"plan": "control", "unit_amount": 12900, "interval": "month"},
    "price_1TbcnhGkcGZTLqrPklUxFvRc": {"plan": "control", "unit_amount": 128400, "interval": "year"},
    "price_1TbcniGkcGZTLqrPGRwaFxgZ": {"plan": "command", "unit_amount": 29900, "interval": "month"},
    "price_1TbcniGkcGZTLqrPhzsyjkTj": {"plan": "command", "unit_amount": 298800, "interval": "year"},
    # 2026-08 voice-included list (new signups)
    "price_1U2SQDGkcGZTLqrP1ZTTdpgJ": {"plan": "node", "unit_amount": 5900, "interval": "month"},
    "price_1U2SQtGkcGZTLqrPylFQGJMm": {"plan": "node", "unit_amount": 58800, "interval": "year"},
    "price_1U2SQOGkcGZTLqrPssKHr0bX": {"plan": "control", "unit_amount": 14900, "interval": "month"},
    "price_1U2SQtGkcGZTLqrPE2cE8JIo": {"plan": "control", "unit_amount": 148800, "interval": "year"},
    "price_1U2SQtGkcGZTLqrPRHfZZSEm": {"plan": "command", "unit_amount": 34900, "interval": "month"},
    "price_1U2SQtGkcGZTLqrPKAoonF7g": {"plan": "command", "unit_amount": 349200, "interval": "year"},
}


def init_stripe(settings: Settings) -> None:
    stripe.api_key = settings.stripe_secret_key


def unit_amount_cents_for_plan_price(price_id: str | None) -> int | None:
    """Return Stripe unit_amount cents for a known platform plan Price id."""
    if not price_id:
        return None
    info = STRIPE_PLAN_PRICE_AMOUNTS.get(str(price_id).strip())
    if not info:
        return None
    return int(info["unit_amount"])


def billing_interval_for_plan_price(price_id: str | None) -> str | None:
    if not price_id:
        return None
    info = STRIPE_PLAN_PRICE_AMOUNTS.get(str(price_id).strip())
    if not info:
        return None
    return str(info["interval"])


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
        **LEGACY_STRIPE_PLAN_PRICE_IDS,
    }
    # Ignore blank env mappings so "" keys cannot collide and swallow real price ids.
    cleaned = {str(k): v for k, v in price_to_plan.items() if str(k or "").strip()}
    mapped = cleaned.get(price_id)
    if mapped:
        return mapped
    # Amount catalog covers current + legacy even if env drifts.
    catalog = STRIPE_PLAN_PRICE_AMOUNTS.get(str(price_id).strip())
    if catalog:
        return str(catalog["plan"])
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


def voice_minutes_metered_price_for_subscription(settings: Settings) -> str | None:
    """Global metered price for voice-minute overage (same price all tiers)."""
    from app.billing.stripe_voice_minutes_metering import voice_minutes_metered_price_id

    return voice_minutes_metered_price_id(settings) or None


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
        attached_prices.add(research_metered)
    voice_metered = voice_minutes_metered_price_for_subscription(settings)
    if voice_metered and voice_metered not in attached_prices:
        items.append({"price": voice_metered})
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

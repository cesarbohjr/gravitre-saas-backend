"""Destination charges with application fees — platform monetization."""
from __future__ import annotations

from typing import Any

from stripe import StripeClient

from app.samples.stripe_connect_v2.config import StripeConnectSampleConfig


def _application_fee_amount(unit_amount: int, fee_percent: int) -> int:
    """Platform fee in cents for a destination charge."""
    return max(0, (unit_amount * fee_percent) // 100)


def create_checkout_session(
    stripe_client: StripeClient,
    config: StripeConnectSampleConfig,
    *,
    product: dict[str, Any],
    quantity: int = 1,
) -> str:
    """Step 6: Hosted Checkout — buyer pays platform, funds transfer to connected account.

    Uses payment_intent_data.transfer_data.destination + application_fee_amount.
    """
    unit_amount = int(product["unit_amount"])
    connected_account_id = str(product["connected_account_id"])
    price_id = str(product.get("stripe_price_id") or "")

    fee = _application_fee_amount(unit_amount * quantity, config.platform_fee_percent)

    line_item: dict[str, Any]
    if price_id:
        line_item = {"price": price_id, "quantity": quantity}
    else:
        line_item = {
            "price_data": {
                "currency": product.get("currency") or "usd",
                "unit_amount": unit_amount,
                "product_data": {"name": product.get("name") or "Product"},
            },
            "quantity": quantity,
        }

    session = stripe_client.v1.checkout.sessions.create(
        {
            "mode": "payment",
            "line_items": [line_item],
            "payment_intent_data": {
                "application_fee_amount": fee,
                "transfer_data": {"destination": connected_account_id},
            },
            "success_url": (
                f"{config.app_base_url}/samples/stripe-connect/success?session_id={{CHECKOUT_SESSION_ID}}"
            ),
            "cancel_url": f"{config.app_base_url}/samples/stripe-connect/store",
            "metadata": {
                "connected_account_id": connected_account_id,
                "seller_id": str(product.get("seller_id") or ""),
                "stripe_product_id": str(product.get("stripe_product_id") or ""),
            },
        }
    )
    return str(session.url)

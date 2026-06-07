"""Platform-level products — created on the platform, mapped to a connected account."""
from __future__ import annotations

from typing import Any

from stripe import StripeClient

from app.samples.stripe_connect_v2.config import StripeConnectSampleConfig
from app.samples.stripe_connect_v2.store import list_products, save_product


def create_platform_product(
    stripe_client: StripeClient,
    config: StripeConnectSampleConfig,
    *,
    seller_id: str,
    connected_account_id: str,
    name: str,
    description: str,
    price_cents: int,
    currency: str = "usd",
) -> dict[str, Any]:
    """Step 5: Create a catalog item on the *platform* (not on the connected account).

    We store connected_account_id in Stripe metadata and in the local JSON store
    so checkout can route funds via destination charges.
    """
    product = stripe_client.v1.products.create(
        {
            "name": name,
            "description": description,
            "default_price_data": {
                "unit_amount": price_cents,
                "currency": currency,
            },
            "metadata": {
                "connected_account_id": connected_account_id,
                "seller_id": seller_id,
            },
        }
    )

    default_price = getattr(product, "default_price", None)
    price_id = default_price if isinstance(default_price, str) else getattr(default_price, "id", None)

    row = save_product(
        config.store_path,
        stripe_product_id=str(product.id),
        stripe_price_id=str(price_id or ""),
        connected_account_id=connected_account_id,
        seller_id=seller_id,
        name=name,
        description=description,
        unit_amount=price_cents,
        currency=currency,
    )
    return row


def list_storefront_products(config: StripeConnectSampleConfig) -> list[dict[str, Any]]:
    """Products for the demo storefront (local index; Stripe is source of truth for prices)."""
    return list_products(config.store_path)

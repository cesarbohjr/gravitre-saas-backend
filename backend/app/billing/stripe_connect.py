"""Stripe Connect helpers for marketplace partner payouts (STA-96)."""
from __future__ import annotations

from typing import Any

import stripe

from app.billing.stripe import init_stripe
from app.config import Settings


def create_express_connect_account(
    settings: Settings,
    *,
    org_id: str,
    org_name: str,
) -> stripe.Account:
    """Create a Stripe Express connected account for a partner org."""
    init_stripe(settings)
    return stripe.Account.create(
        type="express",
        country="US",
        business_profile={"name": org_name[:200] if org_name else "Gravitre Partner"},
        capabilities={
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
        metadata={"org_id": org_id, "source": "gravitre_marketplace"},
    )


def create_connect_onboarding_link(
    settings: Settings,
    *,
    account_id: str,
    return_url: str,
    refresh_url: str,
) -> stripe.AccountLink:
    init_stripe(settings)
    return stripe.AccountLink.create(
        account=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )


def retrieve_connect_account(settings: Settings, account_id: str) -> stripe.Account:
    init_stripe(settings)
    return stripe.Account.retrieve(account_id)


def create_connect_transfer(
    settings: Settings,
    *,
    amount_cents: int,
    currency: str,
    destination_account_id: str,
    metadata: dict[str, Any] | None = None,
) -> stripe.Transfer:
    """Transfer partner earnings to a connected account."""
    init_stripe(settings)
    return stripe.Transfer.create(
        amount=amount_cents,
        currency=currency,
        destination=destination_account_id,
        metadata=metadata or {},
    )

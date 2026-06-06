"""Connected account lifecycle — Accounts v2 create, status, onboarding links."""
from __future__ import annotations

from typing import Any

from stripe import StripeClient

from app.samples.stripe_connect_v2.config import StripeConnectSampleConfig
from app.samples.stripe_connect_v2.store import get_seller, save_seller_mapping


def create_connected_account(
    stripe_client: StripeClient,
    config: StripeConnectSampleConfig,
    *,
    seller_id: str,
    display_name: str,
    contact_email: str,
) -> dict[str, Any]:
    """Step 2: Create a v2 connected account where the *platform* collects fees.

    Uses only the properties from Stripe's Connect v2 guide — never top-level `type`.
    Platform is fees_collector + losses_collector (destination charge model).
    """
    # Accounts v2 — recipient configuration with Express dashboard for sellers
    account = stripe_client.v2.core.accounts.create(
        {
            "display_name": display_name,
            "contact_email": contact_email,
            "identity": {"country": "us"},
            "dashboard": "express",
            "defaults": {
                "responsibilities": {
                    "fees_collector": "application",
                    "losses_collector": "application",
                },
            },
            "configuration": {
                "recipient": {
                    "capabilities": {
                        "stripe_balance": {
                            "stripe_transfers": {"requested": True},
                        },
                    },
                },
            },
        }
    )

    account_id = str(account.id)
    # Persist mapping only — onboarding status is always read from Stripe API live
    save_seller_mapping(
        config.store_path,
        seller_id=seller_id,
        account_id=account_id,
        display_name=display_name,
        contact_email=contact_email,
    )
    return {"account_id": account_id, "seller_id": seller_id}


def create_onboarding_link(
    stripe_client: StripeClient,
    config: StripeConnectSampleConfig,
    *,
    account_id: str,
) -> str:
    """Step 3: Stripe-hosted onboarding via v2 Account Links."""
    return_url = f"{config.app_base_url}/samples/stripe-connect/seller?accountId={account_id}"
    refresh_url = f"{config.app_base_url}/samples/stripe-connect/seller?accountId={account_id}&refresh=1"

    link = stripe_client.v2.core.account_links.create(
        {
            "account": account_id,
            "use_case": {
                "type": "account_onboarding",
                "account_onboarding": {
                    "configurations": ["recipient"],
                    "refresh_url": refresh_url,
                    "return_url": return_url,
                },
            },
        }
    )
    return str(link.url)


def _dig(obj: Any, *path: str) -> Any:
    """Walk nested Stripe objects or dicts."""
    current = obj
    for key in path:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(key)
        else:
            current = getattr(current, key, None)
    return current


def retrieve_account_status(stripe_client: StripeClient, account_id: str) -> dict[str, Any]:
    """Step 4: Always fetch onboarding/payout readiness directly from Stripe (no DB cache)."""
    account = stripe_client.v2.core.accounts.retrieve(
        account_id,
        params={"include": ["configuration.recipient", "requirements"]},
    )

    transfers_status = _dig(
        account,
        "configuration",
        "recipient",
        "capabilities",
        "stripe_balance",
        "stripe_transfers",
        "status",
    )
    requirements_status = _dig(account, "requirements", "summary", "minimum_deadline", "status")

    ready_to_receive_payments = transfers_status == "active"
    onboarding_complete = requirements_status not in {"currently_due", "past_due"}

    return {
        "account_id": account_id,
        "display_name": getattr(account, "display_name", None),
        "contact_email": getattr(account, "contact_email", None),
        "transfers_status": transfers_status,
        "requirements_status": requirements_status,
        "ready_to_receive_payments": ready_to_receive_payments,
        "onboarding_complete": onboarding_complete,
    }


def get_seller_account_id(config: StripeConnectSampleConfig, seller_id: str) -> str | None:
    seller = get_seller(config.store_path, seller_id)
    if not seller:
        return None
    return str(seller.get("account_id") or "") or None

"""Stripe Client factory — all Stripe API calls in this sample go through here."""
from __future__ import annotations

from stripe import StripeClient

from app.samples.stripe_connect_v2.config import StripeConnectSampleConfig, load_config


def get_stripe_client(config: StripeConnectSampleConfig | None = None) -> StripeClient:
    """Return a StripeClient configured from environment variables.

    Step 1 of every flow: build one client and reuse it per request.
    The SDK pins the API version automatically — do not set stripe_version manually.
    """
    cfg = config or load_config()
    # PLACEHOLDER: cfg.stripe_secret_key comes from STRIPE_SECRET_KEY
    return StripeClient(cfg.stripe_secret_key)

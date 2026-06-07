"""Environment configuration for the Stripe Connect v2 sample.

Every value that must be supplied by the operator is read from the environment.
Missing required values raise SampleConfigError with actionable messages.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


class SampleConfigError(RuntimeError):
    """Raised when a required Stripe Connect sample env var is missing."""


@dataclass(frozen=True)
class StripeConnectSampleConfig:
    """Runtime configuration for the Connect v2 demo."""

    # PLACEHOLDER: set STRIPE_SECRET_KEY in your environment (sk_test_... or sk_live_...)
    stripe_secret_key: str
    # PLACEHOLDER: signing secret for *thin* Connect webhooks (whsec_... from Dashboard → Webhooks → thin destination)
    stripe_connect_thin_webhook_secret: str
    # Public base URL for return/refresh links (e.g. https://gravitre.app or http://localhost:8000)
    app_base_url: str
    # Platform fee on destination charges (percent, e.g. 10 = 10%)
    platform_fee_percent: int
    # JSON file used to map demo sellers/products (no DB required for the sample)
    store_path: str


def _require(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise SampleConfigError(
            f"Missing required environment variable {name}. "
            f"Add it to your .env (see backend/.env.example and docs/samples/stripe-connect-v2.md)."
        )
    if name == "STRIPE_SECRET_KEY" and not value.startswith(("sk_test_", "sk_live_")):
        raise SampleConfigError(
            f"{name} must start with sk_test_ or sk_live_. "
            "Create a restricted key in Stripe Dashboard → Developers → API keys."
        )
    if name == "STRIPE_CONNECT_THIN_WEBHOOK_SECRET" and not value.startswith("whsec_"):
        raise SampleConfigError(
            f"{name} must be the signing secret (whsec_...) from your thin webhook destination."
        )
    return value


def load_config() -> StripeConnectSampleConfig:
    """Load sample config or raise SampleConfigError with setup instructions."""
    base_url = (os.environ.get("STRIPE_CONNECT_SAMPLE_BASE_URL") or os.environ.get("PUBLIC_APP_URL") or "").strip()
    if not base_url:
        raise SampleConfigError(
            "Missing STRIPE_CONNECT_SAMPLE_BASE_URL (or PUBLIC_APP_URL). "
            "Example: http://localhost:8000 or https://gravitre-saas-backend-production.up.railway.app"
        )
    fee_raw = (os.environ.get("STRIPE_CONNECT_SAMPLE_PLATFORM_FEE_PERCENT") or "10").strip()
    try:
        fee_percent = int(fee_raw)
    except ValueError as exc:
        raise SampleConfigError("STRIPE_CONNECT_SAMPLE_PLATFORM_FEE_PERCENT must be an integer") from exc

    default_store = os.path.join(os.path.dirname(__file__), "data", "store.json")
    store_path = (os.environ.get("STRIPE_CONNECT_SAMPLE_STORE_PATH") or default_store).strip()

    return StripeConnectSampleConfig(
        stripe_secret_key=_require("STRIPE_SECRET_KEY"),
        stripe_connect_thin_webhook_secret=_require("STRIPE_CONNECT_THIN_WEBHOOK_SECRET"),
        app_base_url=base_url.rstrip("/"),
        platform_fee_percent=max(0, min(100, fee_percent)),
        store_path=store_path,
    )

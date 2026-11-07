"""Immutable target checks shared by isolated billing fixture/proof runners."""
from __future__ import annotations

import os
from urllib.parse import urlsplit

ACCEPTANCE_URL = "https://aadnwmjzrmbvadszroqt.supabase.co"


def require_isolated_target(url: str) -> None:
    """Permit local replay or the explicitly allowlisted dedicated test project."""
    if os.environ.get("BILLING_ACCEPTANCE_ISOLATED") != "1":
        raise ValueError("Isolated billing mode is required")
    parsed = urlsplit(url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or any((parsed.username, parsed.password, parsed.query, parsed.fragment))
            or parsed.path not in {"", "/"}):
        raise ValueError("Invalid isolated billing target")
    if parsed.hostname in {"localhost", "127.0.0.1"}:
        return
    if (url.rstrip("/") != ACCEPTANCE_URL
            or os.environ.get("BILLING_ACCEPTANCE_ALLOWED_URL", "").rstrip("/") != ACCEPTANCE_URL):
        raise ValueError("Refusing billing fixtures/proof against a non-acceptance project")


def verify_test_price(price: dict) -> None:
    """Retain the existing genuine-invoice assertion: USD 59/month, licensed."""
    recurring = price.get("recurring") or {}
    if not (price.get("livemode") is False and price.get("active") is True
            and price.get("currency") == "usd" and price.get("unit_amount") == 5900
            and recurring.get("interval") == "month" and recurring.get("interval_count") == 1
            and recurring.get("usage_type") == "licensed"):
        raise ValueError("Acceptance price must be active test-mode USD 59/month licensed recurring pricing")

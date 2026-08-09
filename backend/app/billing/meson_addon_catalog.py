"""Meson addon catalog honesty helpers.

Scaffolding SKUs from migration 20260428011000 were never product-authorized,
Stripe-wired, or gated via require_addon. Customer-facing APIs must not list them.
"""
from __future__ import annotations

from typing import Any

# Archived scaffolding / retired purchase-gate codes — never sell or Enable.
ARCHIVED_MESON_ADDON_CODES: frozenset[str] = frozenset(
    {
        "multi_language",
        "advanced_analytics",
        "compliance_pack",
        "custom_model_training",
        "voice_interface",
    }
)


def is_customer_facing_billable_addon(row: dict[str, Any]) -> bool:
    """True only for active catalog rows with a real Stripe price (billable)."""
    code = str(row.get("code") or "").strip()
    if not code or code in ARCHIVED_MESON_ADDON_CODES:
        return False
    if row.get("archived_at") is not None:
        return False
    stripe_price = str(row.get("stripe_price_id") or "").strip()
    return bool(stripe_price)

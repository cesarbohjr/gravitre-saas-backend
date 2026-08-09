"""Scaffolding Meson SKUs must never be customer-facing."""
from __future__ import annotations

from app.billing.meson_addon_catalog import (
    ARCHIVED_MESON_ADDON_CODES,
    is_customer_facing_billable_addon,
)


def test_scaffolding_codes_are_archived_set():
    assert "multi_language" in ARCHIVED_MESON_ADDON_CODES
    assert "advanced_analytics" in ARCHIVED_MESON_ADDON_CODES
    assert "compliance_pack" in ARCHIVED_MESON_ADDON_CODES
    assert "custom_model_training" in ARCHIVED_MESON_ADDON_CODES
    assert "voice_interface" in ARCHIVED_MESON_ADDON_CODES


def test_scaffolding_row_not_customer_facing_even_with_price():
    assert not is_customer_facing_billable_addon(
        {
            "code": "multi_language",
            "monthly_price_usd": 79,
            "stripe_price_id": None,
            "archived_at": None,
        }
    )


def test_archived_row_hidden():
    assert not is_customer_facing_billable_addon(
        {
            "code": "future_real",
            "monthly_price_usd": 10,
            "stripe_price_id": "price_x",
            "archived_at": "2026-08-09T00:00:00Z",
        }
    )


def test_stripe_wired_active_is_customer_facing():
    assert is_customer_facing_billable_addon(
        {
            "code": "future_real",
            "monthly_price_usd": 10,
            "stripe_price_id": "price_x",
            "archived_at": None,
        }
    )

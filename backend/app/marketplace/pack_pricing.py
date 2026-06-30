"""Department pack pricing framework (MKT-PACK-PRICING-8.3).

General-purpose tier banding for all paid department packs — not Marketing-specific.
Department packs are **one-time purchases** (unlock/install). Ongoing platform access
(Node/Control/Command subscription) and AI usage are billed separately.

Price points grounded in Phase 8.1 comparable research (June 2026), expressed as
one-time unlock fees rather than recurring pack subscriptions.
"""
from __future__ import annotations

from typing import Any

# Tier band one-time prices (USD cents). Flat per org — not per-seat.
# Requires an active Control or Command platform subscription to install/use.
PACK_TIER_PRICE_CENTS: dict[int, int] = {
    1: 4900,  # Starter: single agent + 1–2 workflows
    2: 14900,  # Multi-agent chain + connector requirements
    3: 29900,  # Full department command-center + advanced feedback loops
}

DEPARTMENT_PACK_PRICING_TYPE = "paid"

# Product decision pending pack-owner sign-off (Phase 6.2 / 8.3):
# Mode B autonomous replanning as optional premium add-on vs included with risk gate.
MODE_B_AUTONOMOUS_ADDON_CENTS = 4900

DEPARTMENT_PACK_SLUG_TIERS: dict[str, int] = {
    "marketing-operations-pack": 2,
}

MIN_PACK_TIER = 1
MAX_PACK_TIER = 3


def resolve_pack_tier(asset: dict[str, Any]) -> int | None:
    raw = asset.get("pack_tier")
    if raw is None:
        slug = str(asset.get("slug") or "")
        return DEPARTMENT_PACK_SLUG_TIERS.get(slug)
    try:
        tier = int(raw)
    except (TypeError, ValueError):
        return None
    if MIN_PACK_TIER <= tier <= MAX_PACK_TIER:
        return tier
    return None


def expected_price_cents_for_pack_tier(tier: int) -> int:
    if tier not in PACK_TIER_PRICE_CENTS:
        raise ValueError(f"invalid pack tier: {tier}")
    return PACK_TIER_PRICE_CENTS[tier]


def validate_department_pack_pricing(asset: dict[str, Any]) -> dict[str, Any]:
    """Return normalized pricing fields for a department_pack asset."""
    asset_type = str(asset.get("asset_type") or "")
    if asset_type != "department_pack":
        return {
            "pricing_type": asset.get("pricing_type") or "free",
            "price_cents": int(asset.get("price_cents") or 0),
            "pack_tier": asset.get("pack_tier"),
        }

    tier = resolve_pack_tier(asset)
    if tier is None:
        return {
            "pricing_type": asset.get("pricing_type") or "free",
            "price_cents": int(asset.get("price_cents") or 0),
            "pack_tier": None,
        }

    expected = expected_price_cents_for_pack_tier(tier)
    pricing_type = str(asset.get("pricing_type") or DEPARTMENT_PACK_PRICING_TYPE)
    price_cents = int(asset.get("price_cents") or expected)
    return {
        "pricing_type": pricing_type,
        "price_cents": price_cents,
        "pack_tier": tier,
        "expected_price_cents": expected,
        "price_matches_tier_band": price_cents == expected,
    }

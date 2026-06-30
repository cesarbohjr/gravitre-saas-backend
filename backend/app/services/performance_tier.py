"""Map MODE_CONFIG modes to performance tier labels for observability."""
from __future__ import annotations

from app.operators.assistant_mode_config import normalize_mode

TIER_0 = "tier_0"
TIER_1 = "tier_1"
TIER_2 = "tier_2"
TIER_3 = "tier_3"

MODE_TO_TIER = {
    "fast": TIER_1,
    "standard": TIER_2,
    "reasoning": TIER_3,
    "agent": TIER_3,
}


def mode_to_tier(mode: str | None) -> str:
    return MODE_TO_TIER.get(normalize_mode(mode), TIER_2)


def tier_label_for_mode(mode: str | None) -> str:
    """Human-readable tier name aligned with the performance spec."""
    tier = mode_to_tier(mode)
    return {
        TIER_0: "Tier 0 — Instant cache",
        TIER_1: "Tier 1 — Fast RAG",
        TIER_2: "Tier 2 — Standard",
        TIER_3: "Tier 3 — Deep research",
    }.get(tier, tier)

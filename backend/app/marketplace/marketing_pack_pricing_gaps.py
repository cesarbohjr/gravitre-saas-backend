"""STA-300 / STA-301: Department pack pricing framework + Marketing Operations Pack checkout audit."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

PricingAuditState = Literal["exists", "partial", "missing"]
PricingScope = Literal["framework", "marketing_pack_live", "open_gap"]

REPO_ROOT = Path(__file__).resolve().parents[3]
PACK_TIER_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260709120000_marketplace_pack_tier.sql"
ONE_TIME_PRICING_MIGRATION = (
    REPO_ROOT / "supabase" / "migrations" / "20260709130000_department_pack_one_time_pricing.sql"
)
PRICING_TESTS = REPO_ROOT / "backend" / "tests" / "marketplace" / "test_department_pack_pricing.py"
MARKETING_PACK_SLUG = "marketing-operations-pack"
MARKETING_PACK_PRICE_CENTS = 14900
MARKETING_PACK_TIER = 2


@dataclass(frozen=True)
class PackPricingCapability:
    key: str
    display_name: str
    scope: PricingScope
    audit_state: PricingAuditState
    related_issue: str
    notes: str
    module_path: str | None = None
    symbol: str | None = None


PACK_PRICING_CAPABILITIES: tuple[PackPricingCapability, ...] = (
    PackPricingCapability(
        key="pack_tier_migration",
        display_name="marketplace_assets.pack_tier migration",
        scope="framework",
        audit_state="exists",
        related_issue="STA-300",
        notes="20260709120000_marketplace_pack_tier.sql adds tier column.",
    ),
    PackPricingCapability(
        key="one_time_pricing_migration",
        display_name="Department pack one-time paid pricing migration",
        scope="framework",
        audit_state="exists",
        related_issue="STA-300",
        notes="20260709130000_department_pack_one_time_pricing.sql.",
    ),
    PackPricingCapability(
        key="pack_pricing_module",
        display_name="pack_pricing.py tier bands + validation",
        scope="framework",
        audit_state="exists",
        related_issue="STA-300",
        notes="PACK_TIER_PRICE_CENTS $49/$149/$299; validate_department_pack_pricing().",
        module_path="app.marketplace.pack_pricing",
        symbol="validate_department_pack_pricing",
    ),
    PackPricingCapability(
        key="mode_b_pricing_signoff",
        display_name="Mode B pricing product sign-off (STA-294)",
        scope="framework",
        audit_state="exists",
        related_issue="STA-300",
        notes="Included at Tier 2 with risk gate; MODE_B_AUTONOMOUS_ADDON_CENTS reserved.",
        module_path="app.marketplace.pack_pricing",
        symbol="MODE_B_PRICING_MODEL",
    ),
    PackPricingCapability(
        key="marketing_pack_tier_2_seed",
        display_name="marketing-operations-pack Tier 2 seed",
        scope="marketing_pack_live",
        audit_state="exists",
        related_issue="STA-301",
        notes="seed_catalog.py pack_tier=2, pricing_type=paid.",
    ),
    PackPricingCapability(
        key="marketing_pack_price_14900",
        display_name="Marketing Operations Pack $149 one-time (14900 cents)",
        scope="marketing_pack_live",
        audit_state="exists",
        related_issue="STA-301",
        notes="price_cents=14900 matches tier 2 band.",
    ),
    PackPricingCapability(
        key="install_entitlement_gating",
        display_name="Install entitlement gating (402 PAYMENT_REQUIRED)",
        scope="marketing_pack_live",
        audit_state="exists",
        related_issue="STA-301",
        notes="assert_install_entitlement blocks paid install without purchase.",
        module_path="app.marketplace.entitlements",
        symbol="assert_install_entitlement",
    ),
    PackPricingCapability(
        key="stripe_checkout_payment_mode",
        display_name="Stripe Checkout one-time payment mode",
        scope="marketing_pack_live",
        audit_state="exists",
        related_issue="STA-301",
        notes="create_asset_checkout_session uses mode=payment for paid assets.",
        module_path="app.marketplace.entitlements",
        symbol="create_asset_checkout_session",
    ),
    PackPricingCapability(
        key="pricing_unit_tests",
        display_name="Department pack pricing unit tests",
        scope="marketing_pack_live",
        audit_state="exists",
        related_issue="STA-301",
        notes="test_department_pack_pricing.py covers tier bands + checkout.",
    ),
    PackPricingCapability(
        key="tier_eligibility_checkout_gating",
        display_name="Platform tier eligibility enforced at checkout",
        scope="open_gap",
        audit_state="missing",
        related_issue="STA-299",
        notes="pack_pricing documents Control/Command requirement; checkout does not enforce platform tier.",
        module_path="app.marketplace.entitlements",
        symbol="create_asset_checkout_session",
    ),
)

ALL_PACK_PRICING_CAPABILITIES = PACK_PRICING_CAPABILITIES


def _module_source_path(module_path: str) -> Path | None:
    relative = module_path.replace(".", "/") + ".py"
    candidate = REPO_ROOT / "backend" / relative
    return candidate if candidate.is_file() else None


def _symbol_exists(module_path: str, symbol: str) -> bool:
    source_path = _module_source_path(module_path)
    if source_path is not None:
        text = source_path.read_text(encoding="utf-8")
        return symbol in text
    if importlib.util.find_spec(module_path) is None:
        return False
    module = importlib.import_module(module_path)
    return getattr(module, symbol, None) is not None


def _marketing_pack_seed() -> Any | None:
    try:
        from app.marketplace.seed_catalog import catalog_assets_by_slug

        return catalog_assets_by_slug().get(MARKETING_PACK_SLUG)
    except Exception:  # noqa: BLE001
        return None


def _marketing_pack_pricing_seed_valid() -> bool:
    pack = _marketing_pack_seed()
    if pack is None:
        return False
    return (
        str(getattr(pack, "pricing_type", "") or "") == "paid"
        and int(getattr(pack, "price_cents", 0) or 0) == MARKETING_PACK_PRICE_CENTS
        and int(getattr(pack, "pack_tier", 0) or 0) == MARKETING_PACK_TIER
    )


def _checkout_uses_payment_mode() -> bool:
    path = _module_source_path("app.marketplace.entitlements")
    if path is None:
        return False
    text = path.read_text(encoding="utf-8")
    fn = text.split("def create_asset_checkout_session", 1)
    if len(fn) < 2:
        return False
    body = fn[1].split("\ndef ", 1)[0]
    return 'mode = "subscription"' in body and '"payment"' in body


def _tier_eligibility_at_checkout() -> bool:
    path = _module_source_path("app.marketplace.entitlements")
    if path is None:
        return False
    text = path.read_text(encoding="utf-8")
    fn = text.split("def create_asset_checkout_session", 1)
    if len(fn) < 2:
        return False
    body = fn[1].split("\ndef ", 1)[0]
    markers = ("platform_tier", "assert_platform_tier", "Control", "Command", "pack_tier_eligibility")
    return any(marker in body for marker in markers)


def _mode_b_signoff_documented() -> bool:
    path = _module_source_path("app.marketplace.pack_pricing")
    if path is None:
        return False
    text = path.read_text(encoding="utf-8")
    return "MODE_B_PRICING_MODEL" in text and "included_with_risk_gate" in text


def _resolve_live_state(cap: PackPricingCapability) -> PricingAuditState:
    if cap.key == "pack_tier_migration":
        return "exists" if PACK_TIER_MIGRATION.is_file() else "missing"

    if cap.key == "one_time_pricing_migration":
        return "exists" if ONE_TIME_PRICING_MIGRATION.is_file() else "missing"

    if cap.key == "marketing_pack_tier_2_seed":
        pack = _marketing_pack_seed()
        if pack is None:
            return "missing"
        return "exists" if int(getattr(pack, "pack_tier", 0) or 0) == MARKETING_PACK_TIER else "partial"

    if cap.key == "marketing_pack_price_14900":
        return "exists" if _marketing_pack_pricing_seed_valid() else "missing"

    if cap.key == "stripe_checkout_payment_mode":
        return "exists" if _checkout_uses_payment_mode() else "missing"

    if cap.key == "pricing_unit_tests":
        return "exists" if PRICING_TESTS.is_file() else "missing"

    if cap.key == "mode_b_pricing_signoff":
        return "exists" if _mode_b_signoff_documented() else "partial"

    if cap.key == "tier_eligibility_checkout_gating":
        return "exists" if _tier_eligibility_at_checkout() else "missing"

    if cap.module_path and cap.symbol:
        if not _symbol_exists(cap.module_path, cap.symbol):
            return "missing"
        return cap.audit_state

    return cap.audit_state


def audit_marketing_pack_pricing() -> dict[str, Any]:
    """Return STA-300/301 pricing checklist with live verification."""
    rows: list[dict[str, Any]] = []
    missing_count = 0
    partial_count = 0
    exists_count = 0

    for cap in ALL_PACK_PRICING_CAPABILITIES:
        live_state = _resolve_live_state(cap)
        if live_state == "missing":
            missing_count += 1
        elif live_state == "partial":
            partial_count += 1
        else:
            exists_count += 1

        rows.append(
            {
                "key": cap.key,
                "displayName": cap.display_name,
                "scope": cap.scope,
                "relatedIssue": cap.related_issue,
                "documentedState": cap.audit_state,
                "liveState": live_state,
                "stateMatchesDoc": live_state == cap.audit_state,
                "notes": cap.notes,
            }
        )

    framework_rows = [row for row in rows if row["scope"] == "framework"]
    live_rows = [row for row in rows if row["scope"] == "marketing_pack_live"]
    gap_rows = [row for row in rows if row["scope"] == "open_gap"]

    framework_ready = all(row["liveState"] == "exists" for row in framework_rows)
    marketing_live_ready = all(row["liveState"] == "exists" for row in live_rows)

    return {
        "issues": ["STA-300", "STA-301"],
        "packSlug": MARKETING_PACK_SLUG,
        "relatedIssues": ["STA-294", "STA-299"],
        "recommendation": (
            "Framework and Marketing Operations Pack $149 checkout are live; enforce platform tier "
            "eligibility at checkout before scaling additional department packs"
        ),
        "summary": {
            "total": len(rows),
            "missing": missing_count,
            "partial": partial_count,
            "exists": exists_count,
            "frameworkReady": framework_ready,
            "marketingPackLiveReady": marketing_live_ready,
            "marketingPackPriceCents": MARKETING_PACK_PRICE_CENTS,
            "marketingPackTier": MARKETING_PACK_TIER,
            "tierEligibilityCheckoutMissing": not _tier_eligibility_at_checkout(),
            "v1Ready": framework_ready and marketing_live_ready,
        },
        "framework": framework_rows,
        "marketingPackLive": live_rows,
        "openGaps": gap_rows,
        "capabilities": rows,
    }

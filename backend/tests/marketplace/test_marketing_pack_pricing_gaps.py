"""STA-300/301: Marketing pack pricing audit."""
from __future__ import annotations

from app.marketplace.marketing_pack_pricing_gaps import (
    ALL_PACK_PRICING_CAPABILITIES,
    MARKETING_PACK_PRICE_CENTS,
    audit_marketing_pack_pricing,
)


def test_audit_returns_sta300_301_structure():
    report = audit_marketing_pack_pricing()
    assert report["issues"] == ["STA-300", "STA-301"]
    assert report["packSlug"] == "marketing-operations-pack"
    assert len(report["capabilities"]) == len(ALL_PACK_PRICING_CAPABILITIES)
    assert len(report["framework"]) == 4
    assert len(report["marketingPackLive"]) == 5
    assert len(report["openGaps"]) == 1


def test_framework_ready():
    report = audit_marketing_pack_pricing()
    by_key = {row["key"]: row for row in report["framework"]}
    assert all(row["liveState"] == "exists" for row in report["framework"])
    assert by_key["pack_pricing_module"]["liveState"] == "exists"
    assert report["summary"]["frameworkReady"] is True


def test_marketing_pack_live_checkout():
    report = audit_marketing_pack_pricing()
    by_key = {row["key"]: row for row in report["marketingPackLive"]}
    assert by_key["marketing_pack_price_14900"]["liveState"] == "exists"
    assert by_key["install_entitlement_gating"]["liveState"] == "exists"
    assert by_key["stripe_checkout_payment_mode"]["liveState"] == "exists"
    assert report["summary"]["marketingPackPriceCents"] == MARKETING_PACK_PRICE_CENTS
    assert report["summary"]["marketingPackLiveReady"] is True


def test_tier_eligibility_gap():
    report = audit_marketing_pack_pricing()
    assert report["openGaps"][0]["key"] == "tier_eligibility_checkout_gating"
    assert report["openGaps"][0]["liveState"] == "missing"
    assert report["summary"]["tierEligibilityCheckoutMissing"] is True


def test_v1_ready():
    report = audit_marketing_pack_pricing()
    assert report["summary"]["v1Ready"] is True


def test_documented_states_match_live():
    report = audit_marketing_pack_pricing()
    assert all(row["stateMatchesDoc"] for row in report["capabilities"])

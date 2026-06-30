"""STA-299: Marketing pack reusability audit."""
from __future__ import annotations

from app.marketplace.marketing_pack_reusability_gaps import (
    ALL_REUSABILITY_CAPABILITIES,
    audit_marketing_pack_reusability,
)


def test_audit_returns_sta299_structure():
    report = audit_marketing_pack_reusability()
    assert report["issue"] == "STA-299"
    assert report["packSlug"] == "marketing-operations-pack"
    assert "STA-290" in report["relatedIssues"]
    assert len(report["capabilities"]) == len(ALL_REUSABILITY_CAPABILITIES)
    assert len(report["generalPrimitives"]) == 7
    assert len(report["marketingSpecific"]) == 2
    assert len(report["openUncertainties"]) == 1


def test_general_primitives_mostly_exist():
    report = audit_marketing_pack_reusability()
    by_key = {row["key"]: row for row in report["generalPrimitives"]}
    assert by_key["graph_handoff_agent_chains"]["liveState"] == "exists"
    assert by_key["department_pack_marketplace_type"]["liveState"] == "exists"
    assert by_key["mode_ab_feedback_toggle"]["liveState"] == "exists"
    assert by_key["pack_tier_pricing_framework"]["liveState"] == "exists"
    assert by_key["one_time_entitlement_path"]["liveState"] == "exists"
    assert report["summary"]["packPricingFrameworkShipped"] is True
    assert report["summary"]["modeAbToggleShipped"] is True


def test_batch_and_rejection_partial():
    report = audit_marketing_pack_reusability()
    by_key = {row["key"]: row for row in report["generalPrimitives"]}
    assert by_key["batch_partial_approval"]["liveState"] == "partial"
    assert by_key["rejection_upstream_routing"]["liveState"] == "partial"
    assert report["summary"]["batchPartialApprovalPartial"] is True


def test_marketing_specific_and_tier_uncertainty():
    report = audit_marketing_pack_reusability()
    marketing = {row["key"]: row for row in report["marketingSpecific"]}
    assert marketing["linkedin_publish_connector"]["liveState"] == "partial"
    assert marketing["post_publish_engagement_metrics"]["liveState"] == "exists"
    uncertainty = report["openUncertainties"][0]
    assert uncertainty["key"] == "tier_eligibility_checkout_gating"
    assert uncertainty["liveState"] == "missing"
    assert report["summary"]["tierEligibilityCheckoutMissing"] is True


def test_general_primitives_not_all_exists_due_to_partial():
    report = audit_marketing_pack_reusability()
    assert report["summary"]["generalPrimitivesReady"] is False
    assert report["summary"]["futurePackBlockers"] == []
    assert report["summary"]["nextPackReady"] is True


def test_documented_states_match_live():
    report = audit_marketing_pack_reusability()
    assert all(row["stateMatchesDoc"] for row in report["capabilities"])

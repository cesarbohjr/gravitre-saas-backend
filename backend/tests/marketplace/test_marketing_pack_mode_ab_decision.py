"""STA-294: Marketing pack Mode A/B feedback product decision checklist."""
from __future__ import annotations

from app.marketplace.marketing_pack_mode_ab_decision import (
    MODE_AB_DECISION_CHECKLIST,
    audit_marketing_pack_mode_ab_decision,
)


def test_audit_returns_sta294_structure():
    report = audit_marketing_pack_mode_ab_decision()
    assert report["issue"] == "STA-294"
    assert report["engineeringAuditIssue"] == "STA-293"
    assert report["signOffState"] == "approved"
    assert report["summary"]["productSignOffComplete"] is True
    assert len(report["decisions"]) == len(MODE_AB_DECISION_CHECKLIST)


def test_mode_a_default_confirmed():
    report = audit_marketing_pack_mode_ab_decision()
    default = next(row for row in report["decisions"] if row["key"] == "default_feedback_mode")
    assert default["engineeringRecommendation"] == "mode_a"
    assert default["status"] == "resolved"
    assert default["productDecision"] == "mode_a"
    assert report["packDefaultFeedbackMode"] == "mode_a"
    assert report["summary"]["canShipModeADefault"] is True


def test_mode_b_go_live_gate_confirmed():
    report = audit_marketing_pack_mode_ab_decision()
    gate = next(row for row in report["decisions"] if row["key"] == "mode_b_go_live_gate")
    assert gate["status"] == "resolved"
    assert gate["productDecision"] == "infrastructure_required_before_enable"
    assert report["summary"]["modeBGoLiveGate"] == "infrastructure_required_before_enable"


def test_mode_b_shipping_signed_off_opt_in_only():
    report = audit_marketing_pack_mode_ab_decision()
    shipping = next(row for row in report["decisions"] if row["key"] == "mode_b_shipping")
    assert shipping["status"] == "resolved"
    assert shipping["productDecision"] == "opt_in_only"
    assert report["summary"]["modeBShippingDecisionPending"] is False
    assert report["summary"]["modeBShippingApproved"] is True


def test_mode_b_not_ship_ready_until_infrastructure():
    report = audit_marketing_pack_mode_ab_decision()
    assert report["summary"]["canShipModeB"] is False
    assert report["summary"]["modeBInfrastructureReady"] is False


def test_engineering_items_still_blocked():
    report = audit_marketing_pack_mode_ab_decision()
    guardrails = [row for row in report["decisions"] if row["category"] == "guardrail"]
    toggle = next(row for row in report["decisions"] if row["key"] == "feedback_mode_toggle")
    assert len(guardrails) == 3
    assert all(row["status"] == "blocked" for row in guardrails)
    assert toggle["status"] == "blocked"
    assert report["summary"]["engineeringBlocked"] == 4
    assert report["summary"]["pending"] == 0


def test_mode_b_pricing_signed_off_included_with_risk_gate():
    report = audit_marketing_pack_mode_ab_decision()
    pricing = next(row for row in report["decisions"] if row["key"] == "mode_b_pricing_model")
    assert pricing["status"] == "resolved"
    assert pricing["productDecision"] == "included_with_risk_gate"
    assert report["summary"]["modeBPricingModel"] == "included_with_risk_gate"
    assert report["summary"]["pricingPlaceholderDocumented"] is True


def test_links_sta293_feedback_audit():
    report = audit_marketing_pack_mode_ab_decision()
    loop = report["feedbackLoopAudit"]
    assert loop["modeBMissing"] == 5
    assert "post_publish_marketing_metrics" in loop["packBlockers"]

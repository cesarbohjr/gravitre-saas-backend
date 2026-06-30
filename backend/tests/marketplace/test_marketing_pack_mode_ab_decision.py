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
    assert report["signOffState"] == "awaiting"
    assert len(report["decisions"]) == len(MODE_AB_DECISION_CHECKLIST)


def test_engineering_recommends_mode_a_default():
    report = audit_marketing_pack_mode_ab_decision()
    default = next(row for row in report["decisions"] if row["key"] == "default_feedback_mode")
    assert default["engineeringRecommendation"] == "mode_a"
    assert default["status"] == "pending"
    assert report["summary"]["canShipModeADefault"] is True


def test_mode_b_not_ship_ready():
    report = audit_marketing_pack_mode_ab_decision()
    assert report["summary"]["modeBShippingDecisionPending"] is True
    assert report["summary"]["canShipModeB"] is False
    assert report["summary"]["modeBInfrastructureReady"] is False


def test_mode_b_guardrails_blocked_pending_infrastructure():
    report = audit_marketing_pack_mode_ab_decision()
    guardrails = [row for row in report["decisions"] if row["category"] == "guardrail"]
    assert len(guardrails) == 3
    assert all(row["status"] == "blocked" for row in guardrails)


def test_pricing_placeholder_documented():
    report = audit_marketing_pack_mode_ab_decision()
    pricing = next(row for row in report["decisions"] if row["key"] == "mode_b_pricing_model")
    assert pricing["status"] == "pending"
    assert report["summary"]["pricingPlaceholderDocumented"] is True


def test_links_sta293_feedback_audit():
    report = audit_marketing_pack_mode_ab_decision()
    loop = report["feedbackLoopAudit"]
    assert loop["modeBMissing"] == 5
    assert "post_publish_marketing_metrics" in loop["packBlockers"]

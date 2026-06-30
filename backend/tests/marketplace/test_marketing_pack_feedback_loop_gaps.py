"""STA-293: Marketing pack feedback loop audit (Mode A / Mode B)."""
from __future__ import annotations

from app.marketplace.marketing_pack_feedback_loop_gaps import (
    ALL_FEEDBACK_CAPABILITIES,
    MODE_A_CAPABILITIES,
    MODE_B_CAPABILITIES,
    SHARED_FEEDBACK_CAPABILITIES,
    audit_marketing_pack_feedback_loop,
)


def test_audit_returns_sta293_structure():
    report = audit_marketing_pack_feedback_loop()
    assert report["issue"] == "STA-293"
    assert report["productDecisionTicket"] == "STA-294"
    assert report["recommendedDefault"] == "mode_a"
    assert len(report["capabilities"]) == len(ALL_FEEDBACK_CAPABILITIES)
    assert len(report["modeA"]) == len(MODE_A_CAPABILITIES)
    assert len(report["modeB"]) == len(MODE_B_CAPABILITIES)
    assert len(report["shared"]) == len(SHARED_FEEDBACK_CAPABILITIES)


def test_mode_a_core_primitives_are_partial_or_exists():
    report = audit_marketing_pack_feedback_loop()
    by_key = {row["key"]: row for row in report["modeA"]}
    for key in (
        "company_intelligence_orchestrator",
        "outcome_attribution",
        "integration_suggestions",
        "optimization_suggestions",
    ):
        assert by_key[key]["liveState"] in {"partial", "exists"}
        assert by_key[key]["stateMatchesDoc"] is True


def test_mode_a_human_approval_gate_exists():
    report = audit_marketing_pack_feedback_loop()
    gate = next(row for row in report["modeA"] if row["key"] == "human_approval_gate")
    assert gate["liveState"] == "exists"
    assert gate["stateMatchesDoc"] is True


def test_post_publish_marketing_metrics_wired():
    report = audit_marketing_pack_feedback_loop()
    gap = next(row for row in report["modeA"] if row["key"] == "post_publish_marketing_metrics")
    assert gap["liveState"] == "exists"
    assert gap["stateMatchesDoc"] is True
    assert "post_publish_marketing_metrics" not in report["summary"]["packBlockers"]


def test_mode_b_guardrails_and_toggle_shipped():
    report = audit_marketing_pack_feedback_loop()
    by_key = {row["key"]: row for row in report["capabilities"]}
    for key in (
        "per_cycle_behavior_caps",
        "autonomous_rollback",
        "post_hoc_audit_without_approval",
        "feedback_mode_toggle",
        "tone_cadence_auto_shift",
    ):
        assert by_key[key]["liveState"] == "exists"
    assert by_key["autonomous_replanning_loop"]["liveState"] == "partial"
    assert report["summary"]["modeBInfrastructureShipped"] is True


def test_mode_b_capabilities_no_longer_all_missing():
    report = audit_marketing_pack_feedback_loop()
    assert report["summary"]["modeB"]["missing"] == 0
    assert report["summary"]["modeB"]["exists"] >= 4


def test_mode_b_pricing_constant_is_partial():
    report = audit_marketing_pack_feedback_loop()
    pricing = next(row for row in report["shared"] if row["key"] == "mode_b_pricing_constant")
    assert pricing["liveState"] == "partial"
    assert pricing["stateMatchesDoc"] is True


def test_feedback_mode_toggle_exists():
    report = audit_marketing_pack_feedback_loop()
    toggle = next(row for row in report["shared"] if row["key"] == "feedback_mode_toggle")
    assert toggle["liveState"] == "exists"
    assert report["summary"]["awaitingProductSignOff"] is False

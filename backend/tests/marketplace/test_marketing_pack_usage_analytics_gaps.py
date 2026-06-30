"""STA-297: Marketing pack usage analytics audit."""
from __future__ import annotations

from app.marketplace.marketing_pack_usage_analytics_gaps import (
    ALL_USAGE_ANALYTICS_CAPABILITIES,
    audit_marketing_pack_usage_analytics,
)


def test_audit_returns_sta297_structure():
    report = audit_marketing_pack_usage_analytics()
    assert report["issue"] == "STA-297"
    assert report["packSlug"] == "marketing-operations-pack"
    assert "STA-290" in report["relatedIssues"]
    assert len(report["capabilities"]) == len(ALL_USAGE_ANALYTICS_CAPABILITIES)
    assert len(report["partialBatchOutcomes"]) == 7
    assert len(report["hoursSavedMeasurement"]) == 6


def test_batch_approval_runtime_shipped_analytics_missing():
    report = audit_marketing_pack_usage_analytics()
    by_key = {row["key"]: row for row in report["partialBatchOutcomes"]}
    assert by_key["approval_batch_schema"]["liveState"] == "exists"
    assert by_key["approval_batch_service"]["liveState"] == "exists"
    assert by_key["batch_approval_runtime"]["liveState"] == "partial"
    assert by_key["partial_batch_analytics_schema"]["liveState"] == "missing"
    assert by_key["partial_batch_adoption_attribution"]["liveState"] == "missing"
    assert report["summary"]["approvalBatchSchemaShipped"] is True
    assert report["summary"]["partialBatchAnalyticsMissing"] is True


def test_hours_saved_estimate_only_with_labeling():
    report = audit_marketing_pack_usage_analytics()
    by_key = {row["key"]: row for row in report["hoursSavedMeasurement"]}
    assert by_key["catalog_estimated_hours_saved"]["liveState"] == "exists"
    assert by_key["roi_adopted_estimate_heuristic"]["liveState"] == "partial"
    assert by_key["outcome_estimate_labeling_ui"]["liveState"] == "exists"
    assert by_key["ground_truth_hours_measurement"]["liveState"] == "missing"
    assert by_key["measured_vs_estimate_roi_api"]["liveState"] == "missing"
    assert report["summary"]["outcomeEstimateLabelingShipped"] is True
    assert report["summary"]["measuredHoursSavedMissing"] is True
    assert report["summary"]["roiEstimateOnly"] is True


def test_measurement_blockers_without_pack_blockers():
    report = audit_marketing_pack_usage_analytics()
    assert report["summary"]["v1Ready"] is True
    assert report["summary"]["packBlockers"] == []
    assert "partial_batch_analytics_schema" in report["summary"]["measurementBlockers"]
    assert "roi_adopted_estimate_heuristic" in report["summary"]["measurementBlockers"]
    assert report["summary"]["measuredRoiClaimsBlocked"] is True


def test_documented_states_match_live():
    report = audit_marketing_pack_usage_analytics()
    assert all(row["stateMatchesDoc"] for row in report["capabilities"])

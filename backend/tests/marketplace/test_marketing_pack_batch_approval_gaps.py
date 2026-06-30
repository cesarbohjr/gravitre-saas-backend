"""STA-290: Marketing pack batch + partial approval audit."""
from __future__ import annotations

from app.marketplace.marketing_pack_batch_approval_gaps import (
    ALL_BATCH_APPROVAL_CAPABILITIES,
    audit_marketing_pack_batch_approval,
)


def test_audit_returns_sta290_structure():
    report = audit_marketing_pack_batch_approval()
    assert report["issue"] == "STA-290"
    assert report["packSlug"] == "marketing-operations-pack"
    assert len(report["capabilities"]) == len(ALL_BATCH_APPROVAL_CAPABILITIES)
    assert report["summary"]["runtimeShipped"] is True


def test_batch_runtime_and_ui_shipped():
    report = audit_marketing_pack_batch_approval()
    by_key = {row["key"]: row for row in report["capabilities"]}
    assert by_key["approval_batch_schema"]["liveState"] == "exists"
    assert by_key["approval_batch_service"]["liveState"] == "exists"
    assert by_key["partial_item_decisions"]["liveState"] == "exists"
    assert by_key["batch_approval_api"]["liveState"] == "exists"
    assert by_key["batch_approval_ui"]["liveState"] == "exists"
    assert report["summary"]["batchApprovalUiShipped"] is True


def test_routing_partial_analytics_missing():
    report = audit_marketing_pack_batch_approval()
    by_key = {row["key"]: row for row in report["capabilities"]}
    assert by_key["rejection_upstream_routing"]["liveState"] == "partial"
    assert by_key["partial_batch_analytics"]["liveState"] == "missing"
    assert report["summary"]["partialBatchAnalyticsMissing"] is True


def test_v1_ready_without_pack_blockers():
    report = audit_marketing_pack_batch_approval()
    assert report["summary"]["v1Ready"] is True
    assert report["summary"]["packBlockers"] == []


def test_documented_states_match_live():
    report = audit_marketing_pack_batch_approval()
    assert all(row["stateMatchesDoc"] for row in report["capabilities"])

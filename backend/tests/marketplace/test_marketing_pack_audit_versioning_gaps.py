"""STA-296: Marketing pack audit immutability + pack rollback/versioning audit."""
from __future__ import annotations

from app.marketplace.marketing_pack_audit_versioning_gaps import (
    ALL_AUDIT_VERSIONING_CAPABILITIES,
    audit_marketing_pack_audit_versioning,
)


def test_audit_returns_sta296_structure():
    report = audit_marketing_pack_audit_versioning()
    assert report["issue"] == "STA-296"
    assert report["packSlug"] == "marketing-operations-pack"
    assert "STA-274" in report["relatedIssues"]
    assert len(report["capabilities"]) == len(ALL_AUDIT_VERSIONING_CAPABILITIES)
    assert len(report["auditImmutability"]) == 5
    assert len(report["packVersioning"]) == 5


def test_audit_immutability_migration_and_rls_partial():
    report = audit_marketing_pack_audit_versioning()
    by_key = {row["key"]: row for row in report["auditImmutability"]}
    assert by_key["audit_immutability_migration"]["liveState"] == "exists"
    assert by_key["audit_logs_member_read_only"]["liveState"] == "partial"
    assert by_key["audit_events_member_read_only"]["liveState"] == "partial"


def test_retention_purge_is_compliance_blocker():
    report = audit_marketing_pack_audit_versioning()
    by_key = {row["key"]: row for row in report["capabilities"]}
    assert by_key["retention_purge_rpc"]["liveState"] == "partial"
    assert by_key["approval_trail_append_only"]["liveState"] == "missing"
    assert "retention_purge_rpc" in report["summary"]["complianceBlockers"]
    assert report["summary"]["complianceHeavyApprovalTrailsBlocked"] is True


def test_per_asset_rollback_partial_pack_coordinated_missing():
    report = audit_marketing_pack_audit_versioning()
    by_key = {row["key"]: row for row in report["packVersioning"]}
    assert by_key["marketplace_asset_version_history"]["liveState"] == "partial"
    assert by_key["marketplace_asset_rollback"]["liveState"] == "partial"
    assert by_key["department_pack_multi_entity_install"]["liveState"] == "partial"
    assert by_key["pack_coordinated_rollback"]["liveState"] == "missing"
    assert by_key["pack_install_entity_snapshot"]["liveState"] == "missing"
    assert report["summary"]["perAssetRollbackShipped"] is True
    assert report["summary"]["packCoordinatedRollbackMissing"] is True


def test_v1_ready_without_pack_blockers():
    report = audit_marketing_pack_audit_versioning()
    assert report["summary"]["v1Ready"] is True
    assert report["summary"]["packBlockers"] == []


def test_documented_states_match_live():
    report = audit_marketing_pack_audit_versioning()
    assert all(row["stateMatchesDoc"] for row in report["capabilities"])

"""STA-298: Marketing pack post-consolidation discrepancy audit."""
from __future__ import annotations

from app.marketplace.marketing_pack_consolidation_discrepancies import (
    CONSOLIDATION_DISCREPANCIES,
    audit_marketing_pack_consolidation_discrepancies,
)


def test_audit_returns_sta298_structure():
    report = audit_marketing_pack_consolidation_discrepancies()
    assert report["issue"] == "STA-298"
    assert report["packSlug"] == "marketing-operations-pack"
    assert "STA-258" in report["relatedIssues"]
    assert len(report["discrepancies"]) == len(CONSOLIDATION_DISCREPANCIES)
    assert len(report["architecture"]) == 1
    assert len(report["executionAndNaming"]) == 2
    assert len(report["complianceAndDocs"]) == 2


def test_coordination_layer_killed_confirmed():
    report = audit_marketing_pack_consolidation_discrepancies()
    by_key = {row["key"]: row for row in report["discrepancies"]}
    assert by_key["coordination_layer_killed"]["liveState"] == "confirmed"
    assert report["summary"]["coordinationLayerKilled"] is True


def test_execution_core_naming_confirmed():
    report = audit_marketing_pack_consolidation_discrepancies()
    by_key = {row["key"]: row for row in report["discrepancies"]}
    assert by_key["execution_core_naming"]["liveState"] in {"partial", "confirmed"}
    assert report["summary"]["agentIntelligenceIsExecutionPath"] is True


def test_audit_retention_and_connector_counts():
    report = audit_marketing_pack_consolidation_discrepancies()
    by_key = {row["key"]: row for row in report["discrepancies"]}
    assert by_key["audit_retention_purge"]["liveState"] == "confirmed"
    assert by_key["connector_count_undercount"]["liveState"] == "partial"
    assert report["summary"]["auditRetentionPurgeActive"] is True
    assert report["summary"]["oauthProviderCount"] >= 15
    assert report["summary"]["catalogVendorCount"] >= 50


def test_linear_execute_path_split_confirmed():
    report = audit_marketing_pack_consolidation_discrepancies()
    by_key = {row["key"]: row for row in report["discrepancies"]}
    assert by_key["linear_execute_path_split"]["liveState"] == "confirmed"
    assert report["summary"]["graphAndLinearExecutePaths"] is True


def test_documented_states_match_live():
    report = audit_marketing_pack_consolidation_discrepancies()
    assert all(row["stateMatchesDoc"] for row in report["discrepancies"])

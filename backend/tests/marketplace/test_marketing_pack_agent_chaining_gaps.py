"""STA-291: Marketing pack agent chaining audit."""
from __future__ import annotations

from app.marketplace.marketing_pack_agent_chaining_gaps import (
    ALL_AGENT_CHAINING_CAPABILITIES,
    audit_marketing_pack_agent_chaining,
)


def test_audit_returns_sta291_structure():
    report = audit_marketing_pack_agent_chaining()
    assert report["issue"] == "STA-291"
    assert report["packSlug"] == "marketing-operations-pack"
    assert len(report["capabilities"]) == len(ALL_AGENT_CHAINING_CAPABILITIES)
    assert len(report["catalog"]) == 4
    assert len(report["runtime"]) == 3
    assert len(report["versioning"]) == 1


def test_four_agent_chain_shipped():
    report = audit_marketing_pack_agent_chaining()
    by_key = {row["key"]: row for row in report["capabilities"]}
    assert by_key["four_agent_marketing_pack_seed"]["liveState"] == "exists"
    assert by_key["workflow_handoff_next_agent_seed"]["liveState"] == "exists"
    assert by_key["handoff_service_execution"]["liveState"] == "exists"
    assert report["summary"]["fourAgentSeedShipped"] is True
    assert report["summary"]["handoffStepsShipped"] is True


def test_pack_coordinated_semver_missing():
    report = audit_marketing_pack_agent_chaining()
    by_key = {row["key"]: row for row in report["capabilities"]}
    assert by_key["pack_coordinated_semver"]["liveState"] == "missing"
    assert report["summary"]["packCoordinatedSemverMissing"] is True


def test_v1_ready_without_pack_blockers():
    report = audit_marketing_pack_agent_chaining()
    assert report["summary"]["v1Ready"] is True
    assert report["summary"]["packBlockers"] == []


def test_documented_states_match_live():
    report = audit_marketing_pack_agent_chaining()
    assert all(row["stateMatchesDoc"] for row in report["capabilities"])

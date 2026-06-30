"""STA-292: Marketing pack connector gap audit."""
from __future__ import annotations

from app.marketplace.marketing_pack_connector_gaps import (
    MARKETING_PACK_CONNECTOR_GAPS,
    audit_marketing_pack_connectors,
)


def test_audit_returns_all_eight_connectors():
    report = audit_marketing_pack_connectors()
    assert report["issue"] == "STA-292"
    assert len(report["connectors"]) == 8
    assert report["summary"]["total"] == 8


def test_documented_missing_connectors_still_missing():
    report = audit_marketing_pack_connectors()
    by_key = {row["key"]: row for row in report["connectors"]}
    for key in ("dropbox", "adobe_creative_cloud", "engagebay"):
        assert by_key[key]["documentedState"] == "missing"
        assert by_key[key]["liveState"] == "missing"


def test_linkedin_publish_is_partial_and_blocks_pack():
    report = audit_marketing_pack_connectors()
    linkedin = next(row for row in report["connectors"] if row["key"] == "linkedin_publish")
    assert linkedin["liveState"] == "partial"
    assert linkedin["blocksPack"] == "yes"
    assert "linkedin_publish" in report["summary"]["packBlockers"]


def test_shipped_partial_connectors_match_documentation():
    report = audit_marketing_pack_connectors()
    by_key = {row["key"]: row for row in report["connectors"]}
    for key in ("apollo", "notion", "google_drive", "canva"):
        assert by_key[key]["liveState"] == "partial"
        assert by_key[key]["stateMatchesDoc"] is True


def test_gap_registry_covers_sta292_ticket_keys():
    keys = {gap.key for gap in MARKETING_PACK_CONNECTOR_GAPS}
    assert keys == {
        "apollo",
        "notion",
        "google_drive",
        "dropbox",
        "canva",
        "adobe_creative_cloud",
        "engagebay",
        "linkedin_publish",
    }

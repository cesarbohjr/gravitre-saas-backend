from __future__ import annotations

from app.connectors.action_catalog import (
    get_vendor_spec,
    source_action_destination_coverage_report,
)
from app.connectors.action_catalog.integration_taxonomy import source_action_destination_profile


def test_source_action_destination_profile_for_vendor_with_actions() -> None:
    spec = get_vendor_spec("hubspot")
    assert spec is not None
    profile = source_action_destination_profile("hubspot", actions=list(spec.all_actions()))
    assert profile["source"] is True
    assert profile["action"] is True
    assert isinstance(profile["destination"], bool)
    assert isinstance(profile["reason"], str) and profile["reason"]


def test_source_action_destination_coverage_report_shape() -> None:
    report = source_action_destination_coverage_report()
    summary = report["summary"]
    assert summary["vendorCount"] > 0
    assert summary["sourceCount"] >= 0
    assert summary["actionCount"] >= 0
    assert summary["destinationCount"] >= 0
    assert isinstance(report["rows"], list) and report["rows"]
    first = report["rows"][0]
    assert "vendor" in first
    assert "integrationClass" in first
    assert "source" in first and "action" in first and "destination" in first

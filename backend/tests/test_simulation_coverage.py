"""Tests for demo simulation coverage registry (STA-285)."""
from app.connectors.simulation_coverage import (
    DEMO_EXCLUDED_VENDORS,
    HRIS_REFERENCE_VENDOR,
    build_simulation_coverage_report,
    evaluate_vendor_demo_safety,
)


def test_workday_is_demo_excluded():
    assert "workday" in DEMO_EXCLUDED_VENDORS
    row = evaluate_vendor_demo_safety("workday")
    assert row["found"] is True
    assert row["demoExcluded"] is True
    assert row["demoReady"] is False


def test_bamboohr_is_hris_reference():
    row = evaluate_vendor_demo_safety(HRIS_REFERENCE_VENDOR)
    assert row["found"] is True
    assert row["hrisReference"] is True


def test_build_report_has_sharepoint_slice():
    report = build_simulation_coverage_report()
    assert report["issue"] == "STA-285"
    assert "sharePointV4Actions" in report
    assert report["summary"]["vendorCount"] > 0


def test_zero_coverage_blocks_demo():
    report = build_simulation_coverage_report()
    for vendor in report["vendors"]:
        if vendor.get("zeroCoverageTools"):
            assert vendor["demoReady"] is False

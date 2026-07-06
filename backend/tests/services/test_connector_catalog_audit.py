"""Connector catalog end-to-end audit tests."""
from __future__ import annotations

from app.services.connector_catalog_audit import (
    audit_connector_catalog,
    audit_summary,
    top_actions_for_smoke,
    top_vendors_by_implementation,
)


def test_audit_covers_full_catalog():
    rows = audit_connector_catalog()
    assert len(rows) >= 580
    vendors = {row.vendor for row in rows}
    assert len(vendors) >= 60
    assert "hubspot" in vendors
    assert "slack" in vendors


def test_audit_summary_counts():
    summary = audit_summary()
    assert summary["totalActions"] == len(audit_connector_catalog())
    assert summary["implemented"] >= 500
    assert summary["chatExposed"] == summary["implemented"]
    assert summary["schemaMissing"] == 0


def test_hubspot_actions_fully_wired():
    hubspot = [r for r in audit_connector_catalog() if r.vendor == "hubspot"]
    assert len(hubspot) >= 20
    for row in hubspot:
        assert row.input_schema_status != "missing"
        if row.implementation_status != "not_implemented":
            assert row.chat_exposure is True
            assert row.execute_exposure is True
            assert row.structured_results is True
            assert row.multi_step_plans is True


def test_top_vendors_and_actions_for_smoke():
    vendors = top_vendors_by_implementation(10)
    assert len(vendors) == 10
    assert "hubspot" in vendors
    actions = top_actions_for_smoke(50)
    assert len(actions) == 50
    assert all("." in action for action in actions)

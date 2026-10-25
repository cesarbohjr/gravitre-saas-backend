"""Focused verified-source and no-fabrication sweep tests."""
from app.services.intelligence_overview_sweep_worker import assessment_for_org, process_queued_sweep
from unittest.mock import patch
from types import SimpleNamespace


def test_assessment_never_invents_revenue_or_executes_tools():
    with patch("app.services.intelligence_overview_sweep_worker.load_connected_connectors", return_value=[
        {"vendor": "hubspot", "status": "active", "executable": True, "label": "HubSpot"},
        {"vendor": "stripe", "status": "disconnected", "executable": False, "label": "Stripe"},
    ]), patch("app.services.intelligence_overview_sweep_worker.load_usage_by_connector", return_value={"hubspot": 3}):
        report = assessment_for_org(object(), "tenant-a")
    assert report["analysis_type"] == "integration_telemetry_only"
    assert report["connectors"] == ["hubspot"]
    assert report["comprehensive"] is False
    assert report["insights"][0]["business_impact"] is None
    assert report["outcomes"] == []
    assert report["actions"] == []
    assert all("executeUrl" not in rec for rec in report["recommendations"])


class FakeQuery:
    def __init__(self, db):
        self.db = db
        self.filters = {}
        self.write = None
    def update(self, data):
        self.write = data
        return self
    def eq(self, key, value):
        self.filters[key] = value
        return self
    def execute(self):
        if self.filters.get("org_id") != self.db["org_id"] or self.filters.get("id") != self.db["id"]:
            return SimpleNamespace(data=[])
        if self.filters.get("status") != self.db["status"]:
            return SimpleNamespace(data=[])
        self.db.update(self.write)
        return SimpleNamespace(data=[dict(self.db)])


class FakeDb:
    def __init__(self, item):
        self.item = item
    def table(self, name):
        assert name == "intelligence_overview_sweeps"
        return FakeQuery(self.item)


def test_atomic_claim_prevents_duplicate_processing():
    row = {"id": "s-1", "org_id": "tenant-a", "status": "queued"}
    db = FakeDb(dict(row))
    with patch("app.services.intelligence_overview_sweep_worker.assessment_for_org", return_value={"advisory_only": True}):
        assert process_queued_sweep(db, row)["status"] == "partial"
        assert process_queued_sweep(db, row)["status"] == "already_claimed"
    assert db.item["status"] == "partial"

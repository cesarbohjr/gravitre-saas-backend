"""Offline E2E contract: tenant policy -> evidence -> governed action boundary.

Uses real Overview policy and sweep processing against a deterministic in-memory
store; no live provider, Stripe, or tenant credentials. Not production acceptance.
"""
from unittest.mock import patch
from app.services.intelligence_overview_policy import (
    CAPABILITIES, normalize_policy, apply_response_sensitivity, select_enrichment_work,
)
from app.services.intelligence_overview_sweep_worker import process_queued_sweep


class Query:
    def __init__(self, row):
        self.row = row
        self.fields = {}
        self.changes = None
    def update(self, changes):
        self.changes = changes
        return self
    def eq(self, field, value):
        self.fields[field] = value
        return self
    def execute(self):
        if any(self.row.get(k) != v for k, v in self.fields.items()):
            return type("Response", (), {"data": []})()
        self.row.update(self.changes)
        return type("Response", (), {"data": [dict(self.row)]})()


class Db:
    def __init__(self, row):
        self.row = row
    def table(self, table):
        assert table == "intelligence_overview_sweeps"
        return Query(self.row)


def test_seven_policy_controls_evidence_and_no_automatic_execution():
    policy = normalize_policy({name: {"mode": "conservative"} for name in CAPABILITIES})
    assert set(policy) == set(CAPABILITIES)
    context = {"defer_optional": True}
    eligibility = select_enrichment_work(
        {"requires_prediction": True, "requires_causal": True, "requires_graph": True},
        context, policy,
    )
    assert not any(eligibility.values())
    evidence = {"enrichments": {"capabilities": {
        name: {"status": "available", "confidence": .40,
               "data": {"sample": "provider payload"}} for name in CAPABILITIES}},
        "actions": [], "approvals": []}
    filtered = apply_response_sensitivity(evidence, policy)
    assert all("data" not in filtered["enrichments"]["capabilities"][name]
               for name in CAPABILITIES)
    assert filtered["actions"] == []
    assert filtered["approvals"] == []


def test_queued_sweep_runs_once_and_does_not_invent_outcomes():
    item = {"id": "sweep-1", "org_id": "tenant-1", "status": "queued"}
    db = Db(item)
    report = {"analysis_type": "integration_telemetry_only", "advisory_only": True,
              "recommendations": [], "actions": [], "outcomes": [],
              "comprehensive": False}
    with patch("app.services.intelligence_overview_sweep_worker._has_reserved_sweep_unit", return_value=True), \
         patch("app.services.intelligence_overview_sweep_worker._settle_completed_sweep"), \
         patch("app.services.intelligence_overview_sweep_worker.assessment_for_org",
               return_value=report) as analyze:
        result = process_queued_sweep(db, dict(item))
        repeat = process_queued_sweep(db, {"id": "sweep-1", "org_id": "tenant-1"})
    assert result["status"] == "partial"
    assert repeat["status"] == "already_claimed"
    analyze.assert_called_once_with(db, "tenant-1")
    assert item["results"]["outcomes"] == []
    assert item["results"]["actions"] == []

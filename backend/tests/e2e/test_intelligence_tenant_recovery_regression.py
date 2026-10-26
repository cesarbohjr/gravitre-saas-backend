"""Offline negative tenancy, recovery, and provenance regression matrix.

No network/provider accounts. Exercises real service functions and controlled
in-memory connector/sweep state, not made-up HTTP results.
"""
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi import HTTPException

from app.services.intelligence_evidence_recommendations import build_evidence_recommendations
from app.services.intelligence_history_pipeline import (
    Source, ingest_history, match_observations, run_authorized_history_batch,
)
from app.services.intelligence_overview_sweep_worker import (
    process_queued_sweep, reconcile_unsettled_sweep_usage,
)
from app.billing.intelligence_sweep_meter import reserve_sweep


def test_cross_org_source_and_identity_must_never_produce_recommendation():
    records = [
        {"org_id": "tenant-a", "connector_id": "crm", "object_type": "contact", "external_id": "a"},
        {"org_id": "tenant-b", "connector_id": "crm", "object_type": "contact", "external_id": "b"},
    ]
    identity = {"org_id": "tenant-a", "identity_kind": "email", "identity_hash": "a"*64,
        "match_status": "verified_key", "record_references": [
            {"connector_id": "crm", "object_type": "contact", "external_id": "a"},
            {"connector_id": "crm", "object_type": "contact", "external_id": "b"}]}
    assert build_evidence_recommendations(records, [identity], org_id="tenant-a") == []
    assert build_evidence_recommendations(records, [identity], org_id="tenant-b") == []
    assert match_observations([
        {**records[0], "normalized_identity": {"email": "a@example.test"}},
        {**records[1], "normalized_identity": {"email": "a@example.test"}},
    ], org_id="tenant-a") == []


def test_cross_org_injection_and_revoked_permissions_never_fetch_provider():
    from app.services.intelligence_history_adapters import authorized_history_object
    calls = []
    class Adapter:
        def fetch_page(self, *args):
            calls.append(args)
            return {"records": [], "next_cursor": None}
    fake = {"org_id": "tenant-b", "id": "connector-b", "status": "active",
            "type": "hubspot", "config": {"history_sync_enabled": True},
            "verified_read_capabilities": ["contacts.read"]}
    assert authorized_history_object({**fake, "verified_read_capabilities": []}, "contact") is False
    class DB:
        def table(self, name):
            assert name == "intelligence_history_records"
            return self
        def select(self, *_): return self
        def eq(self, *_): return self
        def limit(self, *_): return self
        def execute(self): return SimpleNamespace(data=[])
    result = run_authorized_history_batch(
        DB(), "tenant-a", [fake, {**fake, "org_id": "tenant-a",
             "verified_read_capabilities": []}],
        {"connector-b": Adapter()}, lambda *_: True)
    assert result["receipts"] == []
    assert calls == []


def test_quota_denial_does_not_call_atomic_admission():
    class DB:
        def rpc(self, *_): raise AssertionError("A denied org must not reach RPC")
    with patch("app.billing.intelligence_sweep_meter.entitled_sweep_limit",
               side_effect=HTTPException(status_code=402, detail="denied")):
        with pytest.raises(HTTPException) as err:
            reserve_sweep(DB(), "tenant-b", "actor", {})
    assert err.value.status_code == 402


def test_crashed_settlement_reconciles_only_terminal_own_org_sweep():
    class Query:
        def __init__(self, table, rows):
            self.table, self.rows, self.filters = table, rows, {}
        def select(self, *_): return self
        def eq(self, field, value): self.filters[field] = value; return self
        def limit(self, *_): return self
        def execute(self):
            return SimpleNamespace(data=[dict(r) for r in self.rows[self.table]
                if all(r.get(k) == v for k,v in self.filters.items())])
    class DB:
        def __init__(self):
            self.rows = {
                "intelligence_sweep_usage_ledger": [
                    {"org_id": "a", "sweep_id": "done", "state": "reserved"},
                    {"org_id": "b", "sweep_id": "running", "state": "reserved"}],
                "intelligence_overview_sweeps": [
                    {"org_id": "a", "id": "done", "status": "partial"},
                    {"org_id": "b", "id": "running", "status": "running"}]}
        def table(self, name): return Query(name, self.rows)
    with patch("app.services.intelligence_overview_sweep_worker._settle_completed_sweep") as settle:
        count = reconcile_unsettled_sweep_usage(DB())
    assert count == 1
    assert settle.call_args.args[1:] == ("a", "done")


def test_completion_conflict_cannot_claim_success_or_settle():
    class FakeQuery:
        def __init__(self):
            self.filters = {}
        def update(self, row): self.updated = row; return self
        def eq(self, k, v): self.filters[k] = v; return self
        def execute(self):
            if self.filters.get("status") == "queued":
                return SimpleNamespace(data=[{"status": "running"}])
            return SimpleNamespace(data=[])
    class FakeDB:
        def table(self, table):
            assert table == "intelligence_overview_sweeps"
            return FakeQuery()
    with patch("app.services.intelligence_overview_sweep_worker._has_reserved_sweep_unit", return_value=True), patch(
        "app.services.intelligence_overview_sweep_worker.assessment_for_org",
        return_value={"analysis_type":"integration_telemetry_only"}) as assessment, patch(
        "app.services.intelligence_overview_sweep_worker._settle_completed_sweep"
    ) as settlement:
        result = process_queued_sweep(FakeDB(), {"org_id":"a","id":"sweep","status":"queued"})
    assert result["status"] == "completion_conflict"
    assessment.assert_called_once()
    settlement.assert_not_called()

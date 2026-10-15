"""Audit-log / telemetry retention: off by default, dry run counts only, bounded batches,
legal hold and floors respected, archive written before anything is deleted."""
from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.schedulers import audit_retention_scheduler as sched
from app.services import data_retention as dr
from tests.services.storage_fakes import FakeClient

ORG = "11111111-1111-4111-8111-111111111111"
OTHER = "33333333-3333-4333-8333-333333333333"
HELD = "55555555-5555-4555-8555-555555555555"
NOW = datetime(2027, 10, 13, 3, 0, tzinfo=UTC)


def _settings(**overrides) -> SimpleNamespace:
    base = {
        "audit_retention_days": 365,
        "telemetry_retention_days": 0,
        "audit_retention_dry_run": True,
        "audit_retention_archive_enabled": False,
        "audit_retention_archive_bucket": "audit-archive",
        "audit_retention_batch_size": 2,
        "audit_retention_max_batches_per_run": 50,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _client(candidates: dict[str, dict[str, int]] | None = None, holds: tuple[str, ...] = ()) -> FakeClient:
    client = FakeClient()
    client.tables["org_legal_holds"] = [{"org_id": h, "released_at": None} for h in holds] + [
        {"org_id": OTHER, "released_at": "2026-01-01T00:00:00+00:00"}
    ]
    candidates = candidates if candidates is not None else {"audit_logs": {ORG: 5}, "audit_events": {}}
    client.rpc_handlers["data_retention_candidates"] = lambda p: [
        {"org_id": org, "row_count": n} for org, n in candidates.get(p["p_table"], {}).items()
    ]
    return client


def test_config_defaults_keep_everything():
    s = Settings(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="a",
        supabase_service_role_key="s",
        supabase_jwt_secret="j",
    )
    assert s.audit_retention_days == 0
    assert s.telemetry_retention_days == 0
    assert s.audit_retention_dry_run is True
    assert s.audit_retention_archive_enabled is False
    assert dr.retention_plan(s) == []


def test_off_does_nothing_at_all():
    client = _client()
    out = dr.run_data_retention(client, _settings(audit_retention_days=0), now=NOW)
    assert out == {"status": "off"}
    assert client.calls == []


def test_scheduler_not_started_when_off(monkeypatch):
    monkeypatch.setattr(sched, "get_settings", lambda: _settings(audit_retention_days=0))
    assert sched.start_audit_retention_scheduler() is None


def test_plan_raises_to_floors_and_never_includes_guardrail_events():
    plan = dr.retention_plan(_settings(audit_retention_days=30, telemetry_retention_days=7))
    by_table = {t.table: t for t in plan}
    assert by_table["audit_logs"].days == 365 and by_table["audit_logs"].configured_days == 30
    assert by_table["audit_events"].days == 365
    assert by_table["model_calls"].days == 400
    assert by_table["ai_pipeline_latency"].days == 30
    assert by_table["cognitive_turn_traces"].days == 30
    assert "guardrail_events" not in by_table
    assert not any(t.archive for t in plan if t.table not in dr.AUDIT_TABLES)
    longer = {t.table: t.days for t in dr.retention_plan(_settings(audit_retention_days=730))}
    assert longer["audit_logs"] == 730


def test_dry_run_counts_only_and_writes_a_receipt():
    client = _client({"audit_logs": {ORG: 5, OTHER: 3}, "audit_events": {ORG: 2}})
    out = dr.run_data_retention(client, _settings(audit_retention_days=100), now=NOW)
    assert out["dryRun"] is True and out["status"] == "completed"
    assert out["totals"]["matched"] == 10 and out["totals"]["deleted"] == 0
    assert client.rpc_calls("data_retention_delete_batch") == []
    assert client.rpc_calls("data_retention_fetch_batch") == []
    cutoffs = {c["p_table"]: c["p_cutoff"] for c in client.rpc_calls("data_retention_candidates")}
    assert cutoffs["audit_logs"].startswith("2026-10-13")  # 365-day floor, not 100
    receipt = client.tables["data_retention_runs"][0]
    assert receipt["status"] == "completed" and receipt["dry_run"] is True
    assert receipt["settings"]["tables"]["audit_logs"]["raisedToFloor"] is True
    assert receipt["details"]["audit_logs"]["orgs"][OTHER] == {"matched": 3}
    assert client.uploads == []


def test_deletes_in_bounded_batches_until_a_short_batch():
    client = _client({"audit_logs": {ORG: 5}})
    remaining = {"n": 5}

    def delete_batch(p):
        assert p["p_batch"] == 2 and "p_ids" not in p
        n = min(remaining["n"], p["p_batch"])
        remaining["n"] -= n
        return n

    client.rpc_handlers["data_retention_delete_batch"] = delete_batch
    out = dr.run_data_retention(client, _settings(audit_retention_dry_run=False), now=NOW)
    assert out["status"] == "completed"
    assert out["totals"]["deleted"] == 5
    assert len(client.rpc_calls("data_retention_delete_batch")) == 3  # 2 + 2 + 1
    assert out["totals"]["batches"] == 3


def test_batch_budget_stops_the_run_as_partial():
    client = _client({"audit_logs": {ORG: 100}})
    client.rpc_handlers["data_retention_delete_batch"] = lambda p: p["p_batch"]
    out = dr.run_data_retention(
        client, _settings(audit_retention_dry_run=False, audit_retention_max_batches_per_run=4), now=NOW
    )
    assert out["status"] == "partial"
    assert len(client.rpc_calls("data_retention_delete_batch")) == 4
    assert client.tables["data_retention_runs"][0]["status"] == "partial"


def test_legal_hold_org_is_never_touched_even_if_listed():
    client = _client({"audit_logs": {ORG: 1, HELD: 9}}, holds=(HELD,))
    client.rpc_handlers["data_retention_delete_batch"] = lambda p: 1 if p["p_org_id"] == ORG else 99
    out = dr.run_data_retention(client, _settings(audit_retention_dry_run=False), now=NOW)
    assert {c["p_org_id"] for c in client.rpc_calls("data_retention_delete_batch")} == {ORG}
    assert HELD not in out["details"]["audit_logs"]["orgs"]
    assert out["settings"]["legalHoldOrgs"] == 1


def test_unreadable_legal_holds_fail_closed():
    client = _client({"audit_logs": {ORG: 1}})
    client.table_errors[("org_legal_holds", "select")] = RuntimeError("relation does not exist")
    out = dr.run_data_retention(client, _settings(audit_retention_dry_run=False), now=NOW)
    assert out == {"status": "failed", "error": "legal_holds_unreadable"}
    assert [c for c in client.calls if c[0] == "rpc"] == []


def test_another_running_run_holds_the_lease():
    client = _client()
    client.table_errors[("data_retention_runs", "insert")] = RuntimeError("23505 duplicate key")
    out = dr.run_data_retention(client, _settings(audit_retention_dry_run=False), now=NOW)
    assert out == {"status": "skipped", "reason": "run_in_progress"}
    assert [c for c in client.calls if c[0] == "rpc"] == []


def _archive_client() -> FakeClient:
    client = _client({"audit_logs": {ORG: 3}})
    rows = [
        {"id": f"00000000-0000-4000-8000-00000000000{i}", "org_id": ORG, "action": "x", "created_at": f"2025-0{i}"}
        for i in range(1, 4)
    ]
    state = {"rows": rows}

    def fetch(p):
        return state["rows"][: p["p_batch"]]

    def delete(p):
        ids = set(p["p_ids"])
        before = len(state["rows"])
        state["rows"] = [r for r in state["rows"] if r["id"] not in ids]
        return before - len(state["rows"])

    client.rpc_handlers["data_retention_fetch_batch"] = fetch
    client.rpc_handlers["data_retention_delete_batch"] = delete
    return client


def test_archive_is_uploaded_before_the_same_rows_are_deleted():
    client = _archive_client()
    out = dr.run_data_retention(
        client, _settings(audit_retention_dry_run=False, audit_retention_archive_enabled=True), now=NOW
    )
    assert out["status"] == "completed"
    assert out["totals"]["deleted"] == 3 and out["totals"]["archivedObjects"] == 2
    order = [e[0] if e[0] == "upload" else e[1] for e in client.events]
    order = [e for e in order if e != "data_retention_candidates"]
    # fetch -> upload -> delete, per batch; never a delete before its upload.
    assert order == [
        "data_retention_fetch_batch", "upload", "data_retention_delete_batch",
        "data_retention_fetch_batch", "upload", "data_retention_delete_batch",
    ]
    first = client.uploads[0]
    assert first["bucket"] == "audit-archive"
    assert first["path"].startswith(f"{ORG}/audit_logs/2026-10-13/")
    assert first["path"].endswith("-00001.jsonl.gz")
    assert first["options"]["upsert"] == "false"
    lines = gzip.decompress(first["data"]).decode().splitlines()
    assert [json.loads(line)["id"] for line in lines] == [
        "00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-000000000002",
    ]
    deletes = client.rpc_calls("data_retention_delete_batch")
    assert deletes[0]["p_ids"] == ["00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-000000000002"]


def test_failed_archive_upload_deletes_nothing():
    client = _archive_client()
    client.upload_error = RuntimeError("bucket missing")
    out = dr.run_data_retention(
        client, _settings(audit_retention_dry_run=False, audit_retention_archive_enabled=True), now=NOW
    )
    assert out["status"] == "partial"
    assert client.rpc_calls("data_retention_delete_batch") == []
    assert out["details"]["audit_logs"]["orgs"][ORG]["archiveError"] == "RuntimeError"
    assert out["totals"]["deleted"] == 0


def test_telemetry_is_never_archived_and_uses_its_own_switch():
    client = _client({"model_calls": {ORG: 1}, "ai_pipeline_latency": {}, "cognitive_turn_traces": {}})
    client.rpc_handlers["data_retention_delete_batch"] = lambda p: 1
    out = dr.run_data_retention(
        client,
        _settings(audit_retention_days=0, telemetry_retention_days=10, audit_retention_dry_run=False,
                  audit_retention_archive_enabled=True),
        now=NOW,
    )
    assert set(out["details"]) == {"model_calls", "ai_pipeline_latency", "cognitive_turn_traces"}
    assert client.rpc_calls("data_retention_fetch_batch") == []
    assert client.uploads == []
    assert out["totals"]["deleted"] == 1


def test_rpc_failure_marks_the_receipt_failed():
    client = _client({"audit_logs": {ORG: 1}})

    def boom(_p):
        raise RuntimeError("canceling statement due to statement timeout")

    client.rpc_handlers["data_retention_delete_batch"] = boom
    out = dr.run_data_retention(client, _settings(audit_retention_dry_run=False), now=NOW)
    assert out["status"] == "failed"
    assert client.tables["data_retention_runs"][0]["status"] == "failed"


@pytest.mark.parametrize("dry", [True, False])
def test_receipt_records_mode(dry):
    client = _client({"audit_logs": {}})
    dr.run_data_retention(client, _settings(audit_retention_dry_run=dry), now=NOW)
    assert client.tables["data_retention_runs"][0]["dry_run"] is dry

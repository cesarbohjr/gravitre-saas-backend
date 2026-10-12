"""AI production smoke fixtures: contract workflow row, crash reporting, and the summary gate."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))


def _load(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve their module via sys.modules
    spec.loader.exec_module(module)
    return module


smoke = _load("smoke_ai_production", "smoke-ai-production.py")
summary = _load("smoke_hardening_summary_live", "smoke-hardening-summary-live.py")

ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
USER = "a9f1240f-910a-42ca-aebf-38caeac288c3"
LEGACY_WF = "7d481101-2e41-46e6-904c-d5f73ce32c1e"


class _Query:
    def __init__(self, db: _FakeDb, table: str) -> None:
        self.db, self.table, self.op, self.payload = db, table, "select", None

    def select(self, *_a: Any) -> _Query:
        return self

    def eq(self, *_a: Any) -> _Query:
        return self

    def limit(self, *_a: Any) -> _Query:
        return self

    def insert(self, payload: dict) -> _Query:
        self.op, self.payload = "insert", payload
        return self

    def upsert(self, payload: dict, **_kw: Any) -> _Query:
        self.op, self.payload = "upsert", payload
        return self

    def execute(self) -> Any:
        if self.op == "select":
            return type("R", (), {"data": list(self.db.rows.get(self.table, []))})()
        if self.table == "workflow_versions":
            # Mirrors workflow_versions_workflow_id_fkey -> public.workflows(id).
            contract_ids = {w["id"] for w in self.db.rows.get("workflows", [])}
            if self.payload["workflow_id"] not in contract_ids:
                raise RuntimeError("workflow_versions_workflow_id_fkey violation")
        self.db.writes.append((self.table, self.op, self.payload))
        if self.table == "workflows":
            self.db.rows.setdefault("workflows", []).append(self.payload)
        row = {"id": "ver-1", **self.payload} if self.table == "workflow_versions" else self.payload
        return type("R", (), {"data": [row]})()


class _FakeDb:
    def __init__(self, rows: dict[str, list[dict]]) -> None:
        self.rows = rows
        self.writes: list[tuple[str, str, dict]] = []

    def table(self, name: str) -> _Query:
        return _Query(self, name)


def test_legacy_only_smoke_workflow_gets_contract_row_before_version(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb({"workflow_defs": [{"id": LEGACY_WF}]})
    monkeypatch.setattr(smoke, "_supabase_client", lambda _env: db)

    assert smoke._ensure_abc_workflow({}, ORG, USER) == LEGACY_WF

    tables = [t for t, _op, _p in db.writes]
    assert tables.index("workflows") < tables.index("workflow_versions")
    contract = next(p for t, _op, p in db.writes if t == "workflows")
    assert contract["id"] == LEGACY_WF and contract["org_id"] == ORG
    assert contract["status"] == "active" and contract["environment"] == smoke.ENV_NAME
    assert [n["id"] for n in contract["nodes"]] == ["step_a", "step_b", "step_c"]
    assert contract["edges"] == [{"from": "step_a", "to": "step_b"}, {"from": "step_b", "to": "step_c"}]


def test_contract_row_upserted_even_with_active_version(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb(
        {
            "workflow_defs": [{"id": LEGACY_WF}],
            "workflow_active_versions": [{"active_version_id": "ver-0"}],
        }
    )
    monkeypatch.setattr(smoke, "_supabase_client", lambda _env: db)

    smoke._ensure_abc_workflow({}, ORG, USER)

    assert [(t, op) for t, op, _p in db.writes] == [("workflows", "upsert")]


def test_probe_crash_is_recorded_as_fail_and_report_written(tmp_path: Path) -> None:
    report = smoke.SmokeReport(target="t", org_id=ORG, user_id=USER, started_at="s")
    smoke._run_step(report, "health", lambda: "ok")

    def boom() -> str:
        raise ValueError("insert violates foreign key constraint")

    with pytest.raises(SystemExit):
        smoke._run_step(report, "workflow_execute_abc", boom)
    out = tmp_path / "ai.json"
    smoke._write_report(report, str(out))

    data = json.loads(out.read_text())
    assert data["ok"] is False and data["verdict"] == "FAIL"
    assert data["summary"] == {"pass": 1, "warn": 0, "fail": 1}
    assert summary.artifact_ok(data) is False


PASSING = {"a.json": {"ok": True}, "b.json": {"verdict": "PASS"}, "c.json": {"pass": True}}


def test_summary_fails_when_a_probe_failed_despite_passing_artifacts() -> None:
    outcomes = summary.probe_outcomes(
        {
            "PROBE_OUTCOME_AI_SMOKE": "failure",
            "PROBE_OUTCOME_RESEARCH": "success",
            "SUPABASE_URL": "x",
        }
    )
    passed, oks, failed = summary.evaluate(PASSING, outcomes)
    assert oks == [True, True, True]
    assert passed is False
    assert failed == ["AI_SMOKE"]


@pytest.mark.parametrize("outcome", ["failure", "cancelled", "skipped", ""])
def test_summary_treats_any_non_success_outcome_as_failed(outcome: str) -> None:
    passed, _oks, failed = summary.evaluate(PASSING, {"AI_SMOKE": outcome})
    assert passed is False and failed == ["AI_SMOKE"]


def test_summary_passes_only_when_artifacts_and_probes_all_ok() -> None:
    outcomes = {"AI_SMOKE": "success", "MARKETPLACE": "success"}
    assert summary.evaluate(PASSING, outcomes)[0] is True
    missing = {**PASSING, "b.json": {"missing": True}}
    assert summary.evaluate(missing, outcomes)[0] is False


def test_workflow_passes_every_probe_outcome_to_summary() -> None:
    wf = (REPO / ".github" / "workflows" / "production-hardening-smoke.yml").read_text()
    for step_id, name in (
        ("post_tier5", "POST_TIER5"),
        ("marketplace", "MARKETPLACE"),
        ("ai_smoke", "AI_SMOKE"),
        ("research", "RESEARCH"),
        ("link_check", "LINK_CHECK"),
    ):
        assert f"PROBE_OUTCOME_{name}: ${{{{ steps.{step_id}.outcome }}}}" in wf
    assert "rm -f docs/delivery/smoke-marketplace-production-latest.json" in wf

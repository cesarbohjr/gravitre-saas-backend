"""Per-run time and cost record: attribution, execution time, summary."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services import cost_attribution as ca
from app.services.run_cost_summary import run_cost_summary

RUN = "11111111-1111-1111-1111-111111111111"


class _Table:
    def __init__(self, db, name):
        self.db, self.name, self.op, self.payload, self.filters = db, name, "select", None, {}
        self.start, self.end = 0, None

    def select(self, *_a):
        return self

    def eq(self, k, v):
        self.filters[k] = v
        return self

    def limit(self, *_a):
        return self

    def order(self, *_a):
        return self

    def range(self, start, end):
        self.start, self.end = start, end
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def execute(self):
        if self.op == "insert":
            if self.db.missing_columns and any(k in self.payload for k in ca.ATTRIBUTION_KEYS):
                raise Exception("{'code': 'PGRST204', 'message': \"Could not find the 'run_id' column\"}")
            self.db.inserted.append(dict(self.payload))
            return SimpleNamespace(data=[{"id": "mc-1"}])
        if self.op == "update":
            self.db.rows.setdefault(self.name, [{}])[0].update(self.payload)
            return SimpleNamespace(data=[])
        if self.name == "model_calls" and self.db.missing_columns and "run_id" in self.filters:
            raise Exception("42703 column model_calls.run_id does not exist")
        rows = [r for r in self.db.rows.get(self.name, []) if all(r.get(k, v) == v for k, v in self.filters.items())]
        return SimpleNamespace(data=rows[self.start:self.end + 1 if self.end is not None else None])


class _DB:
    def __init__(self, rows=None, missing_columns=False):
        self.rows: dict[str, list[dict[str, Any]]] = rows or {}
        self.inserted: list = []
        self.missing_columns = missing_columns

    def table(self, name):
        return _Table(self, name)


def test_attribution_context_sets_and_resets():
    assert ca.attribution_fields() == {}
    with ca.attribution(run_id="r1"):
        with ca.attribution(turn_id="t1"):
            assert ca.attribution_fields() == {"run_id": "r1", "turn_id": "t1"}
        assert ca.attribution_fields() == {"run_id": "r1"}
    assert ca.attribution_fields() == {}


def test_attribution_follows_to_thread():
    async def go():
        with ca.attribution(run_id="r2"):
            return await asyncio.to_thread(ca.attribution_fields)

    assert asyncio.run(go()) == {"run_id": "r2"}


def test_insert_model_call_adds_run_id():
    db = _DB()
    with ca.attribution(run_id=RUN):
        ca.insert_model_call(db, {"org_id": "o", "cost_usd": 0.1})
    assert db.inserted == [{"org_id": "o", "cost_usd": 0.1, "run_id": RUN}]


def test_insert_model_call_adds_turn_id_via_bind():
    db = _DB()
    token = ca.bind_turn_attribution("turn-abc")
    try:
        ca.insert_model_call(db, {"org_id": "o", "cost_usd": 0.1})
    finally:
        ca.reset_turn_attribution(token)
    assert db.inserted == [{"org_id": "o", "cost_usd": 0.1, "turn_id": "turn-abc"}]


def test_insert_model_call_keeps_cost_when_columns_missing():
    db = _DB(missing_columns=True)
    with ca.attribution(run_id=RUN):
        ca.insert_model_call(db, {"org_id": "o", "cost_usd": 0.1})
    assert db.inserted == [{"org_id": "o", "cost_usd": 0.1}]


def test_insert_model_call_reraises_other_errors():
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.side_effect = RuntimeError("boom")
    with ca.attribution(run_id=RUN), pytest.raises(RuntimeError):
        ca.insert_model_call(client, {"org_id": "o"})


def test_model_router_log_carries_run_id():
    from app.services.model_router import ModelRouter, TaskType

    db = _DB()
    router = ModelRouter.__new__(ModelRouter)
    router.settings = SimpleNamespace()
    resp = SimpleNamespace(provider="openai", model="m", input_tokens=10, output_tokens=5, latency_ms=3,
                           cost_usd=0.002, cache_hit=False)

    async def go():
        with ca.attribution(run_id=RUN):
            return await router._log_model_call("org-1", TaskType.CLASSIFICATION, resp)

    with patch("app.services.model_router.get_supabase_client", return_value=db):
        assert asyncio.run(go()) == "mc-1"
    assert db.inserted[0]["run_id"] == RUN and db.inserted[0]["cost_usd"] == 0.002


def test_executor_attributes_model_calls_and_accumulates_execution_time():
    from app.workflows import execute as ex

    seen: list = []

    def fake_impl(*_a, **_k):
        seen.append(ca.attribution_fields())
        return ("completed", [], [], False)

    db = _DB({"workflow_runs": [{"id": RUN, "duration_ms": 1000}]})
    with patch.object(ex, "_execute_workflow_steps", side_effect=fake_impl):
        out = ex.execute_workflow_steps(SimpleNamespace(), "org-1", "u", RUN, {"steps": []}, {}, db)
    assert out[0] == "completed"
    assert seen == [{"run_id": RUN}]
    assert ca.attribution_fields() == {}
    assert db.rows["workflow_runs"][0]["duration_ms"] >= 1000


def test_execution_time_failure_never_fails_the_run():
    from app.workflows import execute as ex

    client = MagicMock()
    client.table.side_effect = RuntimeError("db down")
    with patch.object(ex, "_execute_workflow_steps", return_value=("completed", [], [], False)):
        assert ex.execute_workflow_steps(SimpleNamespace(), "o", "u", RUN, {}, {}, client)[0] == "completed"


def _summary_db(missing_columns=False):
    return _DB(
        {
            "workflow_runs": [
                {"id": RUN, "org_id": "org-1", "workflow_id": "wf", "status": "completed", "trigger_type": "freshservice",
                 "approval_status": "approved", "created_at": "2026-10-13T10:00:00+00:00",
                 "completed_at": "2026-10-13T10:05:00+00:00", "duration_ms": 4200}
            ],
            "workflow_steps": [
                {"id": "step-1", "run_id": RUN, "org_id": "org-1", "step_type": "invoke_tool", "status": "completed",
                 "started_at": "2026-10-13T10:04:50+00:00", "output_snapshot": {"outcome_verified": True}},
                {"id": "step-2", "run_id": RUN, "org_id": "org-1", "step_type": "noop", "status": "completed",
                 "started_at": "2026-10-13T10:04:55+00:00"},
            ],
            "model_calls": [
                {"id": "model-1", "org_id": "org-1", "run_id": RUN, "input_tokens": 100, "output_tokens": 20, "cost_usd": 0.0012},
                {"id": "model-2", "org_id": "org-1", "run_id": RUN, "input_tokens": 50, "output_tokens": 10, "cost_usd": "0.0003"},
                {"id": "model-3", "org_id": "org-1", "run_id": "other", "input_tokens": 999, "output_tokens": 0, "cost_usd": 9},
            ],
        },
        missing_columns=missing_columns,
    )


def test_summary_reports_time_cost_and_verified_writes():
    s = run_cost_summary(_summary_db(), "org-1", RUN)
    assert s["time"] == {"execution_ms": 4200, "waiting_ms": 290000, "elapsed_ms": 300000}
    assert s["model"] == {"attributed": True, "calls": 2, "input_tokens": 150, "output_tokens": 30, "cost_usd": "0.001500"}
    assert s["steps"] == {"total": 2, "tool_calls": 1, "verified_writes": 1, "failed": 0, "coverage_complete": True}
    assert s["trigger_type"] == "freshservice"


def test_summary_pages_past_postgrest_row_limit():
    db = _summary_db()
    db.rows["model_calls"] = [
        {"id": f"call-{i}", "org_id": "org-1", "run_id": RUN,
         "input_tokens": 1, "output_tokens": 0, "cost_usd": "0.000001"}
        for i in range(1001)
    ]
    summary = run_cost_summary(db, "org-1", RUN)
    assert summary["model"] == {
        "attributed": True, "calls": 1001, "input_tokens": 1001,
        "output_tokens": 0, "cost_usd": "0.001001",
    }


def test_incomplete_model_pages_do_not_report_an_understated_cost(monkeypatch):
    from app.services import run_cost_summary as service

    original = service._read_pages
    monkeypatch.setattr(service, "_read_pages", lambda query: original(query, max_rows=1))
    summary = run_cost_summary(_summary_db(), "org-1", RUN)
    assert summary["model"]["attributed"] is False
    assert summary["model"]["cost_usd"] is None


def test_summary_says_cost_unknown_not_zero_before_migration():
    s = run_cost_summary(_summary_db(missing_columns=True), "org-1", RUN)
    assert s["model"]["attributed"] is False and s["model"]["cost_usd"] is None


def test_summary_is_org_scoped():
    assert run_cost_summary(_summary_db(), "org-2", RUN) is None


def test_endpoint_rejects_malformed_id_without_db_call():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.auth.dependencies import require_org_member
    from app.config import get_settings
    from app.routers import run_cost

    app = FastAPI()
    app.include_router(run_cost.router)
    app.dependency_overrides[require_org_member] = lambda: ({"user_id": "u"}, "org-1", "member")
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace()
    db = _summary_db()
    with patch.object(run_cost, "shared_service_client", return_value=db):
        client = TestClient(app)
        assert client.get("/api/runs/not-a-uuid/cost").status_code == 404
        ok = client.get(f"/api/runs/{RUN}/cost")
        assert ok.status_code == 200 and ok.json()["model"]["calls"] == 2

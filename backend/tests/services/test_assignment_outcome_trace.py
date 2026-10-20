"""Read-only assignment -> outcome run -> learning delivery trace."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services.outcome_learning_handler import HANDLER_NAME, assignment_outcome_trace


class _Query:
    def __init__(self, table: str, rows: list[dict[str, Any]], calls: list[tuple]) -> None:
        self.table = table
        self.rows = rows
        self.calls = calls

    def select(self, *_a: Any, **_k: Any) -> "_Query":
        return self

    def _filter(self, op: str, col: str, value: Any) -> "_Query":
        self.calls.append((self.table, op, col, value))
        if op == "eq":
            self.rows = [r for r in self.rows if str(r.get(col)) == str(value)]
        elif op == "in":
            self.rows = [r for r in self.rows if str(r.get(col)) in {str(v) for v in value}]
        elif op == "contains":
            self.rows = [
                r for r in self.rows
                if all((r.get(col) or {}).get(k) == v for k, v in value.items())
            ]
        return self

    def eq(self, col: str, value: Any) -> "_Query":
        return self._filter("eq", col, value)

    def in_(self, col: str, value: Any) -> "_Query":
        return self._filter("in", col, value)

    def contains(self, col: str, value: Any) -> "_Query":
        return self._filter("contains", col, value)

    def order(self, *_a: Any, **_k: Any) -> "_Query":
        return self

    def limit(self, *_a: Any) -> "_Query":
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=list(self.rows))


class _Client:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self.tables = tables
        self.calls: list[tuple] = []

    def table(self, name: str) -> _Query:
        return _Query(name, list(self.tables.get(name, [])), self.calls)


def _tables() -> dict[str, list[dict[str, Any]]]:
    return {
        "agent_jobs": [
            {"id": "job-1", "org_id": "org-1", "status": "completed", "finished_at": "t1"},
            {"id": "job-2", "org_id": "org-2", "status": "completed", "finished_at": "t1"},
        ],
        "workflow_runs": [
            {"id": "run-1", "org_id": "org-1", "status": "completed", "completed_at": "t2",
             "parameters": {"source": "assignment", "job_id": "job-1"}},
            {"id": "run-x", "org_id": "org-2", "status": "completed", "completed_at": "t2",
             "parameters": {"source": "assignment", "job_id": "job-1"}},
        ],
        "domain_event_outbox": [
            {"event_id": "evt-1", "org_id": "org-1", "event_type": "execution.outcome_finalized",
             "aggregate_id": "run-1", "status": "delivered", "attempts": 1,
             "delivered_handlers": [HANDLER_NAME], "payload": {"secret": "x"}},
            {"event_id": "evt-x", "org_id": "org-2", "event_type": "execution.outcome_finalized",
             "aggregate_id": "run-x", "status": "delivered", "attempts": 1,
             "delivered_handlers": [HANDLER_NAME]},
        ],
    }


def test_trace_links_job_run_and_learning_delivery_in_one_org():
    client = _Client(_tables())
    trace = assignment_outcome_trace(client, org_id="org-1", job_id="job-1")
    assert trace["found"] is True
    assert [r["id"] for r in trace["runs"]] == ["run-1"]
    assert trace["events"] == [{
        "event_id": "evt-1", "run_id": "run-1", "status": "delivered", "attempts": 1,
        "delivered_handlers": [HANDLER_NAME], "learning_delivered": True,
    }]
    for table in ("agent_jobs", "workflow_runs", "domain_event_outbox"):
        assert (table, "eq", "org_id", "org-1") in client.calls


def test_trace_hides_other_orgs_job():
    trace = assignment_outcome_trace(_Client(_tables()), org_id="org-1", job_id="job-2")
    assert trace == {"found": False, "job": None, "runs": [], "events": []}


def test_pending_or_other_handler_is_not_learning_delivered():
    tables = _tables()
    tables["domain_event_outbox"][0].update(status="pending", delivered_handlers=[])
    trace = assignment_outcome_trace(_Client(tables), org_id="org-1", job_id="job-1")
    assert trace["events"][0]["learning_delivered"] is False
    tables["domain_event_outbox"][0].update(status="delivered", delivered_handlers=["other.handler"])
    trace = assignment_outcome_trace(_Client(tables), org_id="org-1", job_id="job-1")
    assert trace["events"][0]["learning_delivered"] is False


def test_unfinished_job_has_no_run_yet():
    tables = _tables()
    tables["workflow_runs"] = []
    trace = assignment_outcome_trace(_Client(tables), org_id="org-1", job_id="job-1")
    assert trace["found"] is True and trace["runs"] == [] and trace["events"] == []


def test_trace_requires_org_and_job():
    with pytest.raises(ValueError):
        assignment_outcome_trace(_Client({}), org_id="", job_id="job-1")
    with pytest.raises(ValueError):
        assignment_outcome_trace(_Client({}), org_id="org-1", job_id=" ")


def test_trace_route_is_registered_member_scoped():
    from app.routers import admin_intelligence

    paths = {getattr(r, "path", "") for r in admin_intelligence.router.routes}
    assert any(p.endswith("/outcomes/trace") for p in paths)

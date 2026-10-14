"""Per-workflow run summary and department labels for the Workflows list."""
from __future__ import annotations

from app.services.workflow_fleet import summarize_runs, workflow_department_names
from tests.services.fake_supabase_db import FakeSupabaseDB


def test_last_run_is_the_newest_run_whatever_order_rows_arrive_in():
    rows = [
        {"workflow_id": "wf-1", "status": "completed", "created_at": "2026-10-01T08:00:00+00:00"},
        {"workflow_id": "wf-1", "status": "failed", "created_at": "2026-10-12T08:00:00+00:00"},
        {"workflow_id": "wf-1", "status": "completed", "created_at": "2026-10-05T08:00:00+00:00"},
    ]
    summary = summarize_runs(rows)["wf-1"]
    assert summary["lastRun"] == "2026-10-12T08:00:00+00:00"
    assert summary["lastRunStatus"] == "failed"
    assert summary["count"] == 3
    assert summary["completed"] == 2
    assert summary["isRunning"] is False


def test_recent_runs_are_capped_and_read_oldest_to_newest():
    rows = [
        {"workflow_id": "wf-1", "status": "completed" if day % 3 else "failed", "created_at": f"2026-10-{day:02d}T08:00:00+00:00"}
        for day in range(1, 21)
    ]
    recent = summarize_runs(rows)["wf-1"]["recentRuns"]
    assert len(recent) == 12
    assert recent[0]["createdAt"] == "2026-10-09T08:00:00+00:00"
    assert recent[-1]["createdAt"] == "2026-10-20T08:00:00+00:00"


def test_a_live_run_marks_the_workflow_running():
    rows = [
        {"workflow_id": "wf-1", "status": "running", "created_at": "2026-10-13T09:58:00+00:00"},
        {"workflow_id": "wf-2", "status": "completed", "created_at": "2026-10-13T09:00:00+00:00"},
    ]
    summaries = summarize_runs(rows)
    assert summaries["wf-1"]["isRunning"] is True
    assert summaries["wf-2"]["isRunning"] is False


def test_rows_without_a_workflow_are_ignored():
    assert summarize_runs([{"workflow_id": None, "status": "failed"}, "junk"]) == {}  # type: ignore[list-item]


def test_department_names_come_from_assignments_in_this_org():
    db = FakeSupabaseDB()
    db.tables["department_resource_assignments"] = [
        {"org_id": "org-1", "resource_type": "workflow", "resource_id": "wf-1", "department_id": "d-sales"},
        {"org_id": "org-1", "resource_type": "workflow", "resource_id": "wf-1", "department_id": "d-mkt"},
        {"org_id": "org-1", "resource_type": "agent", "resource_id": "wf-1", "department_id": "d-ops"},
        {"org_id": "org-2", "resource_type": "workflow", "resource_id": "wf-1", "department_id": "d-other"},
    ]
    db.tables["departments"] = [
        {"org_id": "org-1", "id": "d-sales", "name": "Sales"},
        {"org_id": "org-1", "id": "d-mkt", "name": "Marketing"},
        {"org_id": "org-1", "id": "d-ops", "name": "Operations"},
        {"org_id": "org-2", "id": "d-other", "name": "Elsewhere"},
    ]
    assert workflow_department_names(db, "org-1", ["wf-1"]) == {"wf-1": ["Marketing", "Sales"]}


def test_department_lookup_failure_leaves_labels_empty():
    class Broken:
        def table(self, _name):
            raise RuntimeError("down")

    assert workflow_department_names(Broken(), "org-1", ["wf-1"]) == {}
    assert workflow_department_names(Broken(), "org-1", []) == {}


class _PagedRuns:
    def __init__(self, rows):
        self.rows, self.ranges = rows, []

    def table(self, _n):
        return self

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def range(self, start, end):
        self.ranges.append((start, end))
        self._slice = (start, end)
        return self

    def execute(self):
        from types import SimpleNamespace

        s, e = self._slice
        return SimpleNamespace(data=self.rows[s : e + 1])


def _rows(n):
    return [{"id": f"r{i:06d}", "workflow_id": "wf-1", "status": "completed", "created_at": "2026-10-01T00:00:00+00:00"} for i in range(n)]


def test_run_history_is_read_in_pages_past_the_postgrest_cap(monkeypatch):
    from app.services import workflow_fleet

    monkeypatch.setattr(workflow_fleet, "RUN_PAGE_SIZE", 1000)
    db = _PagedRuns(_rows(2345))
    rows, truncated = workflow_fleet.read_run_history(db, org_id="o", environment_name="production", workflow_ids=["wf-1"])
    assert len(rows) == 2345
    assert truncated is False
    assert db.ranges == [(0, 999), (1000, 1999), (2000, 2999)]


def test_run_history_exactly_at_ceiling_is_complete_and_past_it_is_not(monkeypatch):
    from app.services import workflow_fleet

    monkeypatch.setattr(workflow_fleet, "RUN_PAGE_SIZE", 10)
    monkeypatch.setattr(workflow_fleet, "RUN_HISTORY_CEILING", 30)
    exact = workflow_fleet.read_run_history(_PagedRuns(_rows(30)), org_id="o", environment_name="production", workflow_ids=["wf-1"])
    assert (len(exact[0]), exact[1]) == (30, False)
    over = workflow_fleet.read_run_history(_PagedRuns(_rows(31)), org_id="o", environment_name="production", workflow_ids=["wf-1"])
    assert (len(over[0]), over[1]) == (30, True)

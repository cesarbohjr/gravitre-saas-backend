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

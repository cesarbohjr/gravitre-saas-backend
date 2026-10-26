"""Retry from the failed step, and link a job to a goal."""
from __future__ import annotations

from app.operators import agent_jobs as jobs
from tests.support.fake_supabase import FakeSupabase

ORG = "org-1"


def _seed(client: FakeSupabase, **over):
    row = {
        "id": "job-1",
        "org_id": ORG,
        "kind": "agent_task",
        "status": "completed",
        "environment": "production",
        "goal_id": "goal-1",
        "payload": {"task": "Add prospects to the Q4 list", "agent_id": "agent-1", "context": {"list": "Q4"}},
        "result": {
            "tool_calls": [
                {"tool": "apollo.lists.list", "result": {"success": True}},
                {"tool": "apollo.organizations.search", "args": {"q": "logistics"},
                 "result": {"success": False, "error": "Plan does not include search API access"}},
            ]
        },
    }
    row.update(over)
    client.tables.setdefault("agent_jobs", []).append(row)


def test_retry_failed_queues_a_job_that_redoes_only_failed_steps():
    client = FakeSupabase()
    _seed(client)
    new = jobs.retry_failed_steps(client, ORG, "job-1", created_by=None)
    assert new is not None and new["id"] != "job-1"
    assert new["status"] == "queued" and new["goal_id"] == "goal-1"
    briefing = new["payload"]["briefing"]
    assert [c["tool"] for c in briefing["already_done"]] == ["apollo.lists.list"]
    assert briefing["redo"][0]["tool"] == "apollo.organizations.search"
    assert briefing["redo"][0]["args"] == {"q": "logistics"}
    assert new["payload"]["context"]["retry_of"] == "job-1"
    assert new["payload"]["task"] == "Add prospects to the Q4 list"


def test_retry_failed_refuses_running_jobs_and_jobs_without_failures():
    client = FakeSupabase()
    _seed(client, status="running")
    assert jobs.retry_failed_steps(client, ORG, "job-1", created_by=None) is None
    other = FakeSupabase()
    _seed(other, result={"tool_calls": [{"tool": "x", "result": {"success": True}}]})
    assert jobs.retry_failed_steps(other, ORG, "job-1", created_by=None) is None
    assert jobs.retry_failed_steps(other, "org-2", "job-1", created_by=None) is None


def test_link_job_goal_sets_and_clears_within_the_org():
    client = FakeSupabase()
    _seed(client, goal_id=None)
    assert jobs.link_job_goal(client, ORG, "job-1", "goal-9")["goal_id"] == "goal-9"
    assert jobs.link_job_goal(client, ORG, "job-1", None)["goal_id"] is None
    assert jobs.link_job_goal(client, "org-2", "job-1", "goal-9") is None

"""Installed listings say "running" only while one of their agents or workflows has work in flight."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.marketplace.run_state import run_states_for_installs
from tests.support.fake_supabase import FakeQuery, FakeSupabase

ORG = "org-1"
NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)


class Query(FakeQuery):
    def in_(self, column, values):
        self._in = (column, set(values))
        return self

    def gte(self, column, value):
        self._gte = (column, value)
        return self

    def _matches(self, row):
        if not super()._matches(row):
            return False
        col_in = getattr(self, "_in", None)
        if col_in and row.get(col_in[0]) not in col_in[1]:
            return False
        col_gte = getattr(self, "_gte", None)
        return not col_gte or str(row.get(col_gte[0]) or "") >= col_gte[1]


class Client(FakeSupabase):
    def table(self, name):
        return Query(self, name)


def _at(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).isoformat()


def test_running_idle_and_last_run():
    client = Client()
    client.tables["agent_jobs"] = [
        {"org_id": ORG, "status": "running", "created_at": _at(1), "agent_id": "agent-a"},
        {"org_id": ORG, "status": "completed", "created_at": _at(5), "agent_id": "agent-b"},
        {"org_id": "org-2", "status": "running", "created_at": _at(1), "agent_id": "agent-b"},
        {"org_id": ORG, "status": "running", "created_at": _at(24 * 40), "agent_id": "agent-b"},
    ]
    client.tables["workflow_runs"] = [
        {"org_id": ORG, "workflow_id": "wf-1", "status": "completed", "created_at": _at(2)},
        {"org_id": ORG, "workflow_id": "wf-2", "status": "running", "created_at": _at(0.5)},
    ]
    installs = {
        # A department pack that installed agent-a and a workflow: busy through its agent.
        "pack": {"installed_entity_type": "department_pack", "installed_entity_id": "p1",
                 "metadata": {"agentIds": ["agent-a"], "workflowIds": ["wf-1"]}},
        # An agent whose only job is done, plus noise from another org and outside the window.
        "agent": {"installed_entity_type": "agent", "installed_entity_id": "agent-b", "metadata": {}},
        "workflow": {"installed_entity_type": "workflow", "installed_entity_id": "wf-2", "metadata": {}},
        "knowledge": {"installed_entity_type": "rag_source", "installed_entity_id": "src-1", "metadata": {}},
    }
    out = run_states_for_installs(client, ORG, installs, now=NOW)
    assert out["pack"] == {"runState": "running", "activeRunCount": 1, "lastRunAt": _at(1)}
    assert out["agent"] == {"runState": "idle", "activeRunCount": 0, "lastRunAt": _at(5)}
    assert out["workflow"]["runState"] == "running"
    assert out["knowledge"] == {"runState": "idle", "activeRunCount": 0, "lastRunAt": None}


def test_no_installs_and_query_errors_stay_idle():
    assert run_states_for_installs(Client(), ORG, {}) == {}

    class Broken(Client):
        def table(self, name):
            raise RuntimeError("down")

    out = run_states_for_installs(
        Broken(), ORG, {"a": {"installed_entity_type": "agent", "installed_entity_id": "x", "metadata": {}}}
    )
    assert out["a"]["runState"] == "idle"

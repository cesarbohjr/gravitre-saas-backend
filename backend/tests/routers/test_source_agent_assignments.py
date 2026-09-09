"""GET /api/sources/{source_id}/agent-assignments — multi-agent KB management."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.routers.sources import list_source_agent_assignments


class _TableQuery:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def is_(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self._rows)


class _FakeClient:
    def __init__(self, *, source_rows, agent_rows, assignment_rows):
        self._source_rows = source_rows
        self._agent_rows = agent_rows
        self._assignment_rows = assignment_rows

    def table(self, name: str):
        if name == "rag_sources":
            return _TableQuery(self._source_rows)
        if name == "agents":
            return _TableQuery(self._agent_rows)
        if name == "agent_knowledge_assignments":
            return _TableQuery(self._assignment_rows)
        raise AssertionError(f"unexpected table {name}")


@pytest.mark.asyncio
async def test_list_source_agent_assignments_marks_assigned_agents(monkeypatch):
    source_id = uuid4()
    org_id = "org-fixture"
    agent_a = str(uuid4())
    agent_b = str(uuid4())
    assignment_id = str(uuid4())

    fake_client = _FakeClient(
        source_rows=[{"id": str(source_id), "name": "Northwind FAQ", "org_id": org_id}],
        agent_rows=[
            {"id": agent_a, "name": "Lead Triage", "department": "Sales", "role": "Revenue ops"},
            {"id": agent_b, "name": "Deal Desk", "department": "Sales", "role": "Pipeline hygiene"},
        ],
        assignment_rows=[
            {
                "id": assignment_id,
                "agent_id": agent_a,
                "enabled": True,
                "label": "Northwind FAQ",
                "last_synced_at": None,
                "freshness_status": "fresh",
            }
        ],
    )

    monkeypatch.setattr(
        "app.routers.sources.create_client",
        lambda *_args, **_kwargs: fake_client,
    )

    result = await list_source_agent_assignments(
        source_id,
        org_id,
        settings=SimpleNamespace(supabase_url="http://test", supabase_service_role_key="key"),
    )

    assert result["sourceName"] == "Northwind FAQ"
    assert result["assignedCount"] == 1
    by_agent = {row["agentId"]: row for row in result["agents"]}
    assert by_agent[agent_a]["assigned"] is True
    assert by_agent[agent_a]["assignmentId"] == assignment_id
    assert by_agent[agent_b]["assigned"] is False
    assert by_agent[agent_b]["assignmentId"] is None

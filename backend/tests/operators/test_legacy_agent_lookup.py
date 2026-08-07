from __future__ import annotations

from unittest.mock import MagicMock

from app.operators.router import (
    _get_legacy_agent,
    _legacy_agent_as_operator,
    _legacy_agent_status_to_operator,
)


def test_legacy_agent_status_to_operator_maps_active():
    assert _legacy_agent_status_to_operator("active") == "active"
    assert _legacy_agent_status_to_operator("processing") == "active"
    assert _legacy_agent_status_to_operator("idle") == "draft"


def test_legacy_agent_as_operator_maps_marketing_seed_row():
    agent = {
        "id": "marketing-id",
        "name": "Marketing Agent",
        "purpose": "Enrolls qualified leads",
        "role": "Marketing Operations",
        "status": "active",
        "stats": {"tasksToday": 9, "successRate": 96},
        "capabilities": ["sequence-enrollment"],
        "config": {"demo": True},
    }
    operator = _legacy_agent_as_operator(agent)
    assert operator["id"] == "marketing-id"
    assert operator["name"] == "Marketing Agent"
    assert operator["status"] == "active"
    assert operator["total_runs"] == 9
    assert operator["success_rate"] == 96.0


def test_legacy_agent_as_operator_does_not_invent_100_without_rate():
    """Phase 5 honesty — missing stats.successRate must not become 100%."""
    agent = {
        "id": "new-id",
        "name": "New Agent",
        "status": "idle",
        "stats": {"tasksToday": 0},
        "capabilities": [],
    }
    operator = _legacy_agent_as_operator(agent)
    assert operator["total_runs"] == 0
    assert operator["success_rate"] == 0.0


def test_get_legacy_agent_reads_agents_table():
    client = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(
        data=[{"id": "marketing-id", "name": "Marketing Agent", "status": "active"}]
    )
    client.table.return_value = chain

    row = _get_legacy_agent(client, "org-1", "marketing-id")

    assert row is not None
    assert row["name"] == "Marketing Agent"
    client.table.assert_called_with("agents")

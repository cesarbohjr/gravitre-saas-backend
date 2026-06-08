from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.operators.agent_intelligence import resolve_agent_record


def test_resolve_agent_record_from_agents_table():
    client = MagicMock()
    with patch(
        "app.services.handoff_service.get_agent",
        return_value={"id": "a1", "name": "Workflow Agent", "systems": ["hubspot"]},
    ):
        row = resolve_agent_record(client, "org-1", "a1")
    assert row is not None
    assert row["name"] == "Workflow Agent"


def test_resolve_agent_record_from_operator_bindings():
    client = MagicMock()
    with patch("app.services.handoff_service.get_agent", return_value=None):
        with patch(
            "app.operators.repository.get_operator",
            return_value={"id": "op-1", "name": "UI Agent", "role": "RevOps", "status": "active", "config": {}},
        ):
            with patch(
                "app.operators.repository.list_operator_bindings",
                return_value=[{"connector_id": "c1"}],
            ):
                with patch(
                    "app.operators.repository.list_connectors_by_ids",
                    return_value=[{"type": "hubspot", "status": "active"}],
                ):
                    row = resolve_agent_record(client, "org-1", "op-1")
    assert row is not None
    assert row["systems"] == ["hubspot"]
    assert row["name"] == "UI Agent"

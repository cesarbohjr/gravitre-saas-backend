"""P27 agent selection contract against the actual production selector.

Exercises the real AgentSelector.select path, persona inference, connector
readiness filtering and explicit-role manifest resolution. Only its external
connector database and optional learned-selection dependency are isolated.
This is not evidence of a fully wired agent -> Play -> approval -> workflow.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_actual_agent_selector_uses_tenant_connected_vendors_and_explicit_role(monkeypatch):
    from app.services import agent_selector

    class ConnectorQuery:
        def __init__(self, rows):
            self.rows = rows
            self.filters = []

        def select(self, columns):
            assert columns == "provider, status"
            return self

        def eq(self, column, value):
            self.filters.append((column, value))
            return self

        def execute(self):
            return SimpleNamespace(data=[
                row for row in self.rows
                if all(row.get(column) == value for column, value in self.filters)
            ])

    org = "synthetic-org-alpha"
    records = [
        {"org_id": org, "provider": "hubspot", "status": "connected"},
        {"org_id": org, "provider": "slack", "status": "disconnected"},
        {"org_id": "synthetic-org-beta", "provider": "slack", "status": "connected"},
    ]
    query_objects = []
    client = MagicMock()

    def table(name):
        assert name == "connectors"
        q = ConnectorQuery(records)
        query_objects.append(q)
        return q

    client.table.side_effect = table
    monkeypatch.setattr(agent_selector, "get_supabase_client", lambda settings: client)
    monkeypatch.setattr(
        "app.services.meta_learning_service.get_meta_learning_service",
        lambda settings: SimpleNamespace(is_enabled=lambda: False),
    )
    selector = agent_selector.AgentSelector(settings=SimpleNamespace())
    classification = {
        "department": "sales",
        "intent": "sales_task",
        "requires_action": True,
        "agent_manifest_role": "qa",
    }
    selected = await selector.select(org, classification)
    assert selected["requires_swarm"] is True
    assert selected["agent_manifest"]["role"] == "qa"
    assert selected["agent_manifest"]["requires_human_approval_for_writes"] is True
    assert "agent_manifest_error" not in selected
    assert query_objects[0].filters == [("org_id", org), ("status", "connected")]

    # Only the tenant's active connections count. Neither another tenant's
    # Slack connection nor this tenant's disconnected one can satisfy readiness.
    available = await selector._get_connected(org)
    assert "hubspot" in available and "platform" in available
    assert "slack" not in available

    # An unrecognized requested specialist cannot silently become a privileged
    # manifest, even when the model marks the task as requiring action.
    unknown = await selector.select(org, {**classification, "agent_manifest_role": "root_admin"})
    assert unknown["agent_manifest_error"] == "unknown_role"
    assert "agent_manifest" not in unknown

    # A prompt-derived or inferred job category must not grant any specialist.
    implicit = await selector.select(org, {
        "department": "engineering",
        "intent": "workflow_execution",
        "requires_action": True,
    })
    assert "agent_manifest" not in implicit

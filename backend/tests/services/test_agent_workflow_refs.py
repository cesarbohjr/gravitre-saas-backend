from __future__ import annotations

from unittest.mock import MagicMock

from app.services.agent_workflow_refs import (
    agent_ids_in_definition,
    find_workflows_referencing_agent,
)


def test_agent_ids_in_definition_collects_nested_refs():
    definition = {
        "steps": [
            {"metadata": {"agent_id": "agent-1"}},
            {"config": {"next_agent_id": "agent-2", "agent_ids": ["agent-3"]}},
        ]
    }
    found = agent_ids_in_definition(definition)
    assert found == {"agent-1", "agent-2", "agent-3"}


def test_find_workflows_referencing_agent_skips_archived():
    client = MagicMock()

    def table(name: str):
        mock = MagicMock()
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.limit.return_value = mock
        if name == "workflow_defs":
            mock.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "wf-1",
                        "name": "Live",
                        "status": "active",
                        "definition": {"steps": [{"metadata": {"agent_id": "agent-1"}}]},
                    },
                    {
                        "id": "wf-2",
                        "name": "Old",
                        "status": "archived",
                        "definition": {"steps": [{"metadata": {"agent_id": "agent-1"}}]},
                    },
                ]
            )
        else:
            mock.execute.return_value = MagicMock(
                data=[{"id": "s1", "enabled": True, "is_enabled": True}]
            )
        return mock

    client.table.side_effect = table
    refs = find_workflows_referencing_agent(client, "org-1", "agent-1")
    assert len(refs) == 1
    assert refs[0]["workflowId"] == "wf-1"
    assert refs[0]["hasEnabledSchedule"] is True

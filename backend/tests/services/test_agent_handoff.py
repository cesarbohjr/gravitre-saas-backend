"""STA-17/18: agent handoff bus and next_agent_id routing."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.handoff_service import (
    build_handoff_briefing,
    execute_agent_step_with_handoff,
    resolve_step_agent_metadata,
)


def test_build_handoff_briefing_from_hubspot_parameters():
    briefing = build_handoff_briefing(
        parameters={
            "contact": {"id": "1", "properties": {"email": "a@b.com"}},
            "hubspot_event": {"subscriptionType": "contact.creation"},
        },
        source_output={"summary": "Qualified", "confidence": 88, "decision": {"qualified": True}},
        step_outputs={"prior": {"ok": True}},
    )
    assert briefing["contact"]["id"] == "1"
    assert briefing["decision"]["qualified"] is True
    assert len(briefing["artifacts"]) >= 2


def test_resolve_step_agent_metadata_prefers_metadata():
    agent_id, next_id, task = resolve_step_agent_metadata(
        {
            "metadata": {
                "agent_id": "sales",
                "next_agent_id": "marketing",
                "task": "Qualify",
            },
            "config": {"agent_id": "ignored"},
        }
    )
    assert agent_id == "sales"
    assert next_id == "marketing"
    assert task == "Qualify"


@pytest.mark.asyncio
async def test_execute_agent_step_routes_to_next_agent():
    settings = SimpleNamespace()
    sales = {"id": "sales", "name": "Sales Agent", "status": "active", "systems": ["hubspot"]}
    marketing = {"id": "marketing", "name": "Marketing Agent", "status": "active", "systems": ["hubspot"]}
    agents_by_id = {"sales": sales, "marketing": marketing}

    def _get_agent(_client, _org_id: str, agent_id: str):
        row = agents_by_id.get(agent_id)
        return dict(row) if row else None

    handoffs_insert = MagicMock()
    handoffs_insert.execute.return_value = MagicMock(
        data=[
            {
                "id": "handoff-1",
                "from_agent_id": "sales",
                "to_agent_id": "marketing",
            }
        ]
    )
    handoffs_table = MagicMock()
    handoffs_table.insert.return_value = handoffs_insert
    handoffs_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    mock_client = MagicMock()

    mock_client.table.side_effect = lambda name: handoffs_table if name == "agent_handoffs" else MagicMock()

    source_output = {"summary": "Lead qualified", "confidence": 90}
    receiver_output = {"summary": "Enrolled in sequence", "confidence": 85}

    with patch("app.services.handoff_service.get_agent", side_effect=_get_agent):
        with patch(
            "app.services.handoff_service.run_agent_task",
            new_callable=AsyncMock,
            side_effect=[source_output, receiver_output],
        ):
            with patch("app.services.handoff_service.write_audit_event"):
                result = await execute_agent_step_with_handoff(
                    settings,
                    org_id="org-1",
                    user_id="user-1",
                    run_id="run-1",
                    step_id="step-1",
                    step_def={
                        "metadata": {
                            "agent_id": "sales",
                            "next_agent_id": "marketing",
                            "task": "Qualify lead",
                            "receiver_task": "Enroll in nurture",
                        },
                    },
                    parameters={"contact": {"id": "42"}},
                    step_outputs={},
                    client=mock_client,
                )

    assert result["handoff"]["to_agent_id"] == "marketing"
    assert result["receiver_output"]["summary"] == "Enrolled in sequence"
    handoffs_table.insert.assert_called_once()
    handoffs_table.update.assert_called()

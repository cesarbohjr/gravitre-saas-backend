"""STA-120: Workflow digital twin simulation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.workflow_twin_predictor_service import resolve_step_tool_action
from app.workflows.digital_twin import _simulate_twin_step
from app.workflows.registry import StepContext


def test_resolve_step_tool_action_for_invoke_tool():
    connector, action = resolve_step_tool_action("invoke_tool", {"action": "hubspot.search_contacts"})
    assert connector == "hubspot"
    assert action == "hubspot.search_contacts"


@pytest.mark.asyncio
async def test_simulate_twin_step_uses_fixture():
    settings = MagicMock()
    context = StepContext(
        settings=settings,
        org_id="org-1",
        user_id="user-1",
        run_id="run-1",
        environment_name="production",
        step_id="step-1",
        step_type="invoke_tool",
        step_index=0,
        config={"action": "hubspot.search_contacts"},
        parameters={},
        step_outputs={},
        client=MagicMock(),
        is_dry_run=True,
    )
    stats: dict[str, int] = {}
    with patch(
        "app.workflows.digital_twin.lookup_connector_fixture",
        return_value={
            "id": "fix-1",
            "response": {"total": 3, "results": [{"id": "1"}]},
        },
    ):
        output = await _simulate_twin_step(settings, context, objective="Find leads", stats=stats)
    assert output["source"] == "fixture"
    assert output["total"] == 3
    assert stats["fixtureHits"] == 1


@pytest.mark.asyncio
async def test_simulate_twin_step_falls_back_to_llm():
    settings = MagicMock()
    context = StepContext(
        settings=settings,
        org_id="org-1",
        user_id="user-1",
        run_id="run-1",
        environment_name="production",
        step_id="step-1",
        step_type="invoke_tool",
        step_index=0,
        config={"action": "hubspot.create_contact"},
        parameters={"email": "a@example.com"},
        step_outputs={},
        client=MagicMock(),
        is_dry_run=True,
    )
    stats: dict[str, int] = {}
    with patch("app.workflows.digital_twin.lookup_connector_fixture", return_value=None):
        with patch(
            "app.workflows.digital_twin.predict_step_outcome",
            new=AsyncMock(
                return_value={
                    "simulated": True,
                    "source": "llm_prediction",
                    "summary": "Would create contact",
                    "output": {"contactId": "pred-1"},
                    "confidence": 0.8,
                }
            ),
        ):
            output = await _simulate_twin_step(settings, context, objective="Create lead", stats=stats)
    assert output["source"] == "llm_prediction"
    assert stats["llmPredictions"] == 1

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.council_workflow_service import (
    build_uncertain_lead_council_workflow_definition,
    council_branch_workflow_id,
    execute_council_step,
    map_recommendation_to_branch,
    resolve_active_branch,
    should_escalate_to_council,
    should_skip_for_branch,
)


def test_map_recommendation_to_branch_uses_output_paths():
    branch = map_recommendation_to_branch(
        "enroll",
        {"enroll": "enroll", "nurture": "nurture"},
        ["enroll", "nurture"],
    )
    assert branch == "enroll"


def test_should_escalate_when_confidence_low():
    assert should_escalate_to_council({"confidence": 60}, threshold=0.75) is True
    assert should_escalate_to_council({"confidence": 90}, threshold=0.75) is False


def test_should_skip_for_branch():
    assert should_skip_for_branch({"when_branch": "enroll"}, "nurture") is True
    assert should_skip_for_branch({"when_branch": "enroll"}, "enroll") is False
    assert should_skip_for_branch({}, "enroll") is False


def test_resolve_active_branch_returns_latest():
    outputs = {
        "council": {"branch": "nurture"},
        "later": {"branch": "enroll"},
    }
    assert resolve_active_branch(outputs) == "enroll"


def test_build_definition_includes_council_and_branch_steps():
    org_id = str(uuid.uuid4())
    definition = build_uncertain_lead_council_workflow_definition(org_id=org_id)
    types = [step["type"] for step in definition["steps"]]
    assert types == ["agent", "council", "agent", "agent"]
    assert definition["steps"][1]["config"]["source_step_id"] == "sales_qualify"
    assert definition["steps"][2]["config"]["when_branch"] == "enroll"


def test_council_workflow_id_stable():
    org = str(uuid.uuid4())
    assert council_branch_workflow_id(org) == council_branch_workflow_id(org)


@pytest.mark.asyncio
async def test_execute_council_step_skips_when_confident():
    org_id = str(uuid.uuid4())
    result = await execute_council_step(
        MagicMock(),
        org_id=org_id,
        user_id="user-1",
        run_id="run-1",
        workflow_id="wf-1",
        step_id="council_escalation",
        config={
            "source_step_id": "sales_qualify",
            "confidence_threshold": 0.75,
            "options": ["enroll", "nurture"],
            "default_branch": "enroll",
        },
        parameters={},
        step_outputs={"sales_qualify": {"confidence": 92, "summary": "enroll"}},
        client=MagicMock(),
        council_service=MagicMock(),
    )
    assert result["escalated"] is False
    assert result["branch"] == "enroll"


@pytest.mark.asyncio
async def test_execute_council_step_escalates_and_branches():
    org_id = str(uuid.uuid4())
    mock_session = MagicMock()
    mock_session.id = "session-1"
    mock_session.final_recommendation = "nurture"
    mock_session.final_confidence = 0.81
    mock_session.decision_method.value = "majority_vote"
    mock_session.dissenting_opinions = []

    council = MagicMock()
    council.start_council = AsyncMock(return_value=mock_session)

    with patch(
        "app.services.council_workflow_service.load_council_agents",
        return_value=[{"name": "Sales Agent", "role": "advocate"}],
    ):
        result = await execute_council_step(
            MagicMock(),
            org_id=org_id,
            user_id="user-1",
            run_id="run-1",
            workflow_id="wf-1",
            step_id="council_escalation",
            config={
                "source_step_id": "sales_qualify",
                "confidence_threshold": 0.75,
                "options": ["enroll", "nurture"],
                "output_paths": {"enroll": "enroll", "nurture": "nurture"},
                "agent_ids": ["agent-1"],
            },
            parameters={},
            step_outputs={"sales_qualify": {"confidence": 55}},
            client=MagicMock(),
            council_service=council,
        )

    assert result["escalated"] is True
    assert result["branch"] == "nurture"
    council.start_council.assert_awaited_once()

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.council_service import AgentCouncilService, AgentOpinion, AgentRole, DecisionMethod


@pytest.fixture
def service() -> AgentCouncilService:
    return AgentCouncilService.__new__(AgentCouncilService)


def test_resolve_vote_weighted(service: AgentCouncilService):
    opinions = [
        {"position": "approve", "confidence": 0.9, "vote_weight": 1.0},
        {"position": "reject", "confidence": 0.4, "vote_weight": 1.0},
        {"position": "approve", "confidence": 0.7, "vote_weight": 1.0},
    ]
    winner, confidence = service._resolve_vote(opinions, DecisionMethod.WEIGHTED_VOTE, [])  # noqa: SLF001
    assert winner == "approve"
    assert confidence > 0.5


def test_has_consensus_majority(service: AgentCouncilService):
    opinions = [
        AgentOpinion(
            agent_name="a1",
            agent_role=AgentRole.ANALYST,
            position="approve",
            confidence=0.8,
            reasoning="ok",
            key_points=[],
            concerns=[],
        ),
        AgentOpinion(
            agent_name="a2",
            agent_role=AgentRole.STRATEGIST,
            position="approve",
            confidence=0.7,
            reasoning="ok",
            key_points=[],
            concerns=[],
        ),
        AgentOpinion(
            agent_name="a3",
            agent_role=AgentRole.SKEPTIC,
            position="reject",
            confidence=0.6,
            reasoning="risk",
            key_points=[],
            concerns=[],
        ),
    ]
    assert service._has_consensus(opinions, DecisionMethod.MAJORITY_VOTE) is True  # noqa: SLF001


@pytest.mark.asyncio
async def test_start_council_completes_and_persists():
    full_service = AgentCouncilService.__new__(AgentCouncilService)
    mock_opinion = AgentOpinion(
        agent_name="a1",
        agent_role=AgentRole.ANALYST,
        position="approve",
        confidence=0.8,
        reasoning="fits criteria",
        key_points=["roi"],
        concerns=[],
        vote_weight=1.0,
    )
    with patch.object(full_service, "_generate_opinion", AsyncMock(return_value=mock_opinion)):
        with patch.object(full_service, "_persist_session") as persist:
            session = await full_service.start_council(
                org_id="org-1",
                workflow_id="wf-1",
                run_id="run-1",
                objective="Approve budget",
                options=["approve", "reject"],
                agents=[{"name": "A", "role": "analyst", "weight": 1.0}],
                max_rounds=2,
            )
    assert session.final_recommendation == "approve"
    assert session.status == "completed"
    persist.assert_called_once()

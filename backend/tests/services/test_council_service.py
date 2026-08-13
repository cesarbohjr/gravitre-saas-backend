from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.council_service import (
    AgentCouncilService,
    AgentOpinion,
    AgentRole,
    CouncilSynthesis,
    DecisionMethod,
    _format_peer_block,
    build_council_system_prompt,
    coerce_council_agent_role,
)


@pytest.fixture
def service() -> AgentCouncilService:
    return AgentCouncilService.__new__(AgentCouncilService)


def test_build_council_system_prompt_includes_agent_identity():
    prompt = build_council_system_prompt({"name": "Analyst One", "role": "analyst"})
    assert "Analyst One" in prompt
    assert "analyst" in prompt


def test_build_council_system_prompt_requires_cross_examination():
    prompt = build_council_system_prompt({"name": "Skeptic", "role": "skeptic"})
    assert "agree, challenge, or revise" in prompt.lower() or (
        "agree" in prompt and "challenge" in prompt and "revise" in prompt
    )
    assert "must be independent" not in prompt.lower()
    assert "do not reference" not in prompt.lower()
    assert "prior peer opinions" in prompt.lower() or "peer" in prompt.lower()


def test_coerce_council_agent_role_maps_demo_agent_roles():
    assert coerce_council_agent_role("Revenue Operations") == AgentRole.STRATEGIST
    assert coerce_council_agent_role("Risk & Compliance") == AgentRole.COMPLIANCE
    assert coerce_council_agent_role("Support Operations") == AgentRole.ADVOCATE
    assert coerce_council_agent_role("Data Platform") == AgentRole.VALIDATOR
    assert coerce_council_agent_role("analyst") == AgentRole.ANALYST


def test_format_peer_block_includes_cross_examine_header():
    peers = [
        {
            "agent_name": "A",
            "agent_role": "analyst",
            "position": "approve",
            "confidence": 0.8,
            "reasoning": "ok",
            "key_points": ["roi"],
            "concerns": [],
        }
    ]
    block = _format_peer_block(peers, [])
    assert "Peer perspectives so far (cross-examine these)" in block
    assert "approve" in block


@pytest.mark.asyncio
async def test_generate_opinion_falls_back_with_demo_agent_role():
    service = AgentCouncilService.__new__(AgentCouncilService)
    service.model_router = AsyncMock()
    service.model_router.complete = AsyncMock(side_effect=RuntimeError("llm unavailable"))
    opinion, is_fallback = await service._generate_opinion(  # noqa: SLF001
        "Assess vendor risk",
        ["proceed", "defer"],
        {"name": "Revenue Ops Agent", "role": "Revenue Operations", "weight": 1.0},
        {"subtasks": []},
        0,
        "org-1",
    )
    assert is_fallback is True
    assert opinion.position == "proceed"
    assert opinion.agent_role == AgentRole.STRATEGIST


@pytest.mark.asyncio
async def test_generate_opinion_prompt_includes_peer_perspectives():
    service = AgentCouncilService.__new__(AgentCouncilService)
    service.model_router = AsyncMock()
    service.model_router.complete = AsyncMock(side_effect=RuntimeError("llm unavailable"))
    peers = [
        {
            "agent_name": "First Speaker",
            "agent_role": "analyst",
            "position": "approve",
            "confidence": 0.9,
            "reasoning": "strong ROI",
            "key_points": ["roi"],
            "concerns": [],
        }
    ]
    await service._generate_opinion(  # noqa: SLF001
        "Approve budget",
        ["approve", "reject"],
        {"name": "Second", "role": "skeptic", "weight": 1.0},
        {},
        0,
        "org-1",
        peer_opinions_this_round=peers,
        previous_rounds=[],
    )
    # Fallback path doesn't call complete successfully, but when it does succeed
    # we still verify the helper formats peers. Call once with a capturing mock.
    captured: dict = {}

    async def _capture(**kwargs):
        captured["prompt"] = kwargs.get("prompt", "")
        raise RuntimeError("stop")

    service.model_router.complete = AsyncMock(side_effect=_capture)
    await service._generate_opinion(  # noqa: SLF001
        "Approve budget",
        ["approve", "reject"],
        {"name": "Second", "role": "skeptic", "weight": 1.0},
        {},
        0,
        "org-1",
        peer_opinions_this_round=peers,
        previous_rounds=[],
    )
    assert "Peer perspectives so far (cross-examine these)" in captured["prompt"]
    assert "First Speaker" in captured["prompt"]
    assert "strong ROI" in captured["prompt"]


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
    with patch.object(
        full_service, "_generate_opinion", AsyncMock(return_value=(mock_opinion, False))
    ):
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
    # Single-agent / no multi-speaker debate: no synthesis entry required.
    assert not any(r.get("type") == "synthesis" for r in session.debate_rounds)
    persist.assert_called_once()


@pytest.mark.asyncio
async def test_start_council_sequential_peers_and_synthesis():
    full_service = AgentCouncilService.__new__(AgentCouncilService)
    call_peer_counts: list[int] = []

    async def _fake_opinion(
        objective,
        options,
        agent,
        evidence,
        round_index,
        org_id,
        peer_opinions_this_round=None,
        previous_rounds=None,
    ):
        peers = peer_opinions_this_round or []
        call_peer_counts.append(len(peers))
        name = str(agent.get("name") or "agent")
        position = "reject" if name == "B" else "approve"
        return (
            AgentOpinion(
                agent_name=name,
                agent_role=coerce_council_agent_role(str(agent.get("role"))),
                position=position,
                confidence=0.75,
                reasoning=f"{name} view; peers_so_far={len(peers)}",
                key_points=["point"],
                concerns=["risk"] if name == "B" else [],
                vote_weight=1.0,
            ),
            False,
        )

    synthesis = CouncilSynthesis(
        final_recommendation="reject",
        synthesis_reasoning="Skeptic B challenged A on risk; council revised to reject.",
        disagreement_trail=["B challenged A's ROI claim; A revised confidence downward"],
        final_confidence=0.72,
    )

    with patch.object(full_service, "_generate_opinion", side_effect=_fake_opinion):
        with patch.object(
            full_service, "_synthesize_debate", AsyncMock(return_value=synthesis)
        ) as synth:
            with patch.object(full_service, "_persist_session") as persist:
                session = await full_service.start_council(
                    org_id="org-1",
                    workflow_id="wf-1",
                    run_id="run-1",
                    objective="Approve risky vendor",
                    options=["approve", "reject"],
                    agents=[
                        {"name": "A", "role": "analyst", "weight": 1.0},
                        {"name": "B", "role": "skeptic", "weight": 1.0},
                    ],
                    max_rounds=1,
                )

    # Sequential: first agent sees 0 peers, second sees 1.
    assert call_peer_counts == [0, 1]
    synth.assert_awaited_once()
    assert session.final_recommendation == "reject"
    assert session.decision_method == DecisionMethod.MAJORITY_VOTE
    synth_entries = [r for r in session.debate_rounds if r.get("type") == "synthesis"]
    assert len(synth_entries) == 1
    assert synth_entries[0]["synthesis_reasoning"] == synthesis.synthesis_reasoning
    assert synth_entries[0]["disagreement_trail"] == synthesis.disagreement_trail
    persist.assert_called_once()
    persisted = persist.call_args[0][1]
    assert any(r.get("type") == "synthesis" for r in persisted.debate_rounds)

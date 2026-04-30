from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.logging import get_logger
from app.services.model_router import TaskType, get_model_router
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


class AgentRole(StrEnum):
    STRATEGIST = "strategist"
    ANALYST = "analyst"
    COMPLIANCE = "compliance"
    VALIDATOR = "validator"
    ADVOCATE = "advocate"
    SKEPTIC = "skeptic"


class DecisionMethod(StrEnum):
    MAJORITY_VOTE = "majority_vote"
    UNANIMOUS = "unanimous"
    WEIGHTED_VOTE = "weighted_vote"
    CHAIR_DECIDES = "chair_decides"


class AgentOpinion(BaseModel):
    agent_name: str
    agent_role: AgentRole
    position: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    key_points: list[str]
    concerns: list[str]
    vote_weight: float = 1.0


class CouncilSession(BaseModel):
    id: str
    workflow_id: str
    run_id: str
    objective: str
    options: list[str]
    decision_method: DecisionMethod
    participating_agents: list[dict]
    debate_rounds: list[dict]
    final_recommendation: str
    final_confidence: float
    dissenting_opinions: list[dict]
    status: str


class AgentCouncilService:
    def __init__(self):
        self.model_router = get_model_router()

    async def start_council(
        self,
        org_id: str,
        workflow_id: str,
        run_id: str,
        objective: str,
        options: list[str],
        agents: list[dict],
        evidence: dict | None = None,
        decision_method: DecisionMethod = DecisionMethod.MAJORITY_VOTE,
        max_rounds: int = 3,
    ) -> CouncilSession:
        rounds: list[dict] = []
        for idx in range(max(1, min(max_rounds, 5))):
            round_opinions: list[AgentOpinion] = []
            for agent in agents:
                opinion = await self._generate_opinion(objective, options, agent, evidence, idx, org_id)
                round_opinions.append(opinion)
            rounds.append({"round": idx + 1, "opinions": [op.model_dump() for op in round_opinions]})
            if self._has_consensus(round_opinions, decision_method):
                break

        final_option, final_confidence = self._resolve_vote(rounds[-1]["opinions"], decision_method, agents)
        dissent = [op for op in rounds[-1]["opinions"] if op.get("position") != final_option]
        session = CouncilSession(
            id=f"{run_id}:{objective[:24]}",
            workflow_id=workflow_id,
            run_id=run_id,
            objective=objective,
            options=options,
            decision_method=decision_method,
            participating_agents=agents,
            debate_rounds=rounds,
            final_recommendation=final_option,
            final_confidence=round(final_confidence, 3),
            dissenting_opinions=dissent,
            status="completed",
        )
        self._persist_session(org_id, session)
        return session

    async def _generate_opinion(
        self,
        objective: str,
        options: list[str],
        agent: dict,
        evidence: dict | None,
        round_index: int,
        org_id: str,
    ) -> AgentOpinion:
        prompt = (
            f"You are agent {agent.get('name')} with role {agent.get('role')}.\n"
            f"Objective: {objective}\n"
            f"Options: {options}\n"
            f"Evidence: {evidence or {}}\n"
            f"Round: {round_index + 1}\n"
            "Return strict JSON."
        )
        fallback = AgentOpinion(
            agent_name=str(agent.get("name") or "agent"),
            agent_role=AgentRole(str(agent.get("role") or "analyst")),
            position=options[0] if options else "defer",
            confidence=0.55,
            reasoning="Insufficient information; defaulting to first viable option.",
            key_points=["default selection"],
            concerns=["limited evidence"],
            vote_weight=float(agent.get("weight") or 1.0),
        )
        try:
            response = await self.model_router.complete(
                task_type=TaskType.AGENT_DEBATE,
                prompt=prompt,
                response_format=AgentOpinion,
                org_id=org_id,
            )
            if response.parsed:
                parsed = AgentOpinion.model_validate(response.parsed)
                parsed.vote_weight = float(agent.get("weight") or parsed.vote_weight or 1.0)
                return parsed
        except Exception as exc:  # noqa: BLE001
            logger.warning("council opinion fallback: %s", str(exc))
        return fallback

    def _has_consensus(self, opinions: list[AgentOpinion], method: DecisionMethod) -> bool:
        if not opinions:
            return False
        votes = [op.position for op in opinions]
        top = max(set(votes), key=votes.count)
        if method == DecisionMethod.UNANIMOUS:
            return votes.count(top) == len(votes)
        if method == DecisionMethod.MAJORITY_VOTE:
            return votes.count(top) > len(votes) / 2
        if method == DecisionMethod.WEIGHTED_VOTE:
            total = sum(op.vote_weight for op in opinions)
            top_weight = sum(op.vote_weight for op in opinions if op.position == top)
            return top_weight > total / 2
        return len(opinions) >= 2

    def _resolve_vote(
        self,
        opinions: list[dict],
        method: DecisionMethod,
        agents: list[dict],
    ) -> tuple[str, float]:
        if not opinions:
            return "defer", 0.0
        if method == DecisionMethod.CHAIR_DECIDES:
            chair_name = str(next((a.get("name") for a in agents if a.get("is_chair")), "") or "")
            for op in opinions:
                if op.get("agent_name") == chair_name:
                    return str(op.get("position") or "defer"), float(op.get("confidence") or 0.5)
        weighted_scores: dict[str, float] = {}
        for op in opinions:
            weight = float(op.get("vote_weight") or 1.0)
            conf = float(op.get("confidence") or 0.0)
            position = str(op.get("position") or "defer")
            weighted_scores[position] = weighted_scores.get(position, 0.0) + (weight * conf)
        winner = max(weighted_scores, key=weighted_scores.get)
        total = sum(weighted_scores.values()) or 1.0
        return winner, weighted_scores[winner] / total

    def _persist_session(self, org_id: str, session: CouncilSession) -> None:
        try:
            settings = get_settings()
            client = get_supabase_client(settings)
            client.table("agent_councils").insert(
                {
                    "org_id": org_id,
                    "workflow_id": session.workflow_id,
                    "run_id": session.run_id,
                    "objective": session.objective,
                    "options": session.options,
                    "decision_method": session.decision_method.value,
                    "participating_agents": session.participating_agents,
                    "debate_rounds": session.debate_rounds,
                    "final_recommendation": session.final_recommendation,
                    "final_confidence": session.final_confidence,
                    "dissenting_opinions": session.dissenting_opinions,
                    "status": session.status,
                }
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("agent_councils insert failed: %s", str(exc))


_council_service_singleton: AgentCouncilService | None = None


def get_council_service() -> AgentCouncilService:
    global _council_service_singleton
    if _council_service_singleton is None:
        _council_service_singleton = AgentCouncilService()
    return _council_service_singleton

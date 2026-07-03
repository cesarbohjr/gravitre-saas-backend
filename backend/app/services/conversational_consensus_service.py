"""Chat-specific consensus refinement with latency guardrails."""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.consensus_personas import CHAT_CONSENSUS_PERSONAS, build_agent_defs
from app.services.council_service import AgentCouncilService, DecisionMethod
from app.services.chat_dialogue_settings import load_chat_dialogue_settings
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


class ConversationalConsensusService:
    """
    Thin wrapper over AgentCouncilService for conversational use.
    10-second timeout with graceful fallback to primary response.
    """

    CONSENSUS_TIMEOUT_SECONDS = 10

    CONSENSUS_TRIGGERS = frozenset(
        {
            "strategic_plan",
            "financial_recommendation",
            "campaign_strategy",
            "workflow_automation_decision",
            "customer_facing_action",
            "executive_summary",
            "data_analysis",
            "workflow_planning",
        }
    )

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._council = AgentCouncilService()

    async def refine_if_warranted(
        self,
        org_id: str,
        request: str,
        primary_response: str,
        classification: dict[str, Any],
        confidence: float,
        dialogue_mode: str,
    ) -> dict[str, Any]:
        dialogue = await load_chat_dialogue_settings(org_id, self.settings)
        if not dialogue.get("consensus_enabled", True):
            return {"response": primary_response, "consensus_used": False}

        intent = str(classification.get("intent") or "")
        should_use = dialogue_mode == "guide" or (
            confidence < 0.55 and intent in self.CONSENSUS_TRIGGERS
        )
        if not should_use or confidence >= 0.75:
            return {"response": primary_response, "consensus_used": False}

        try:
            consensus = await asyncio.wait_for(
                self.deliberate(
                    org_id=org_id,
                    recommendation=primary_response,
                    context={"request": request, "classification": classification},
                    agents=list(CHAT_CONSENSUS_PERSONAS),
                ),
                timeout=self.CONSENSUS_TIMEOUT_SECONDS,
            )
            refined = str(consensus.get("consensus_recommendation") or primary_response)
            summary = str(consensus.get("consensus_explanation") or "")
            if summary and summary not in refined:
                refined = f"{refined}\n\n{summary}"
            return {
                "response": refined,
                "consensus_used": True,
                "confidence": consensus.get("confidence"),
                "minority_opinions": consensus.get("minority_opinions", []),
                "consensus_summary": summary,
            }
        except asyncio.TimeoutError:
            return {
                "response": primary_response,
                "consensus_used": False,
                "note": "Consensus timed out — primary response used.",
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("consensus refine skipped org_id=%s error=%s", org_id, exc)
            return {"response": primary_response, "consensus_used": False}

    async def deliberate(
        self,
        org_id: str,
        recommendation: str,
        context: dict[str, Any],
        agents: list[str],
    ) -> dict[str, Any]:
        agent_defs = build_agent_defs(agents)
        options = [recommendation[:2000], "Revise with more caution and explicit uncertainty"]
        session = await self._council.start_council(
            org_id=org_id,
            workflow_id="chat-consensus",
            run_id=str(uuid.uuid4()),
            objective=str(context.get("request") or "Evaluate assistant recommendation"),
            options=options,
            agents=agent_defs,
            evidence={"classification": context.get("classification")},
            decision_method=DecisionMethod.MAJORITY_VOTE,
            max_rounds=1,
        )
        minority = [
            {
                "agent": op.get("agent_name"),
                "persona": op.get("agent_role") or op.get("role"),
                "position": op.get("position"),
                "concerns": op.get("concerns") or [],
            }
            for op in session.dissenting_opinions
        ]
        result = {
            "consensus_recommendation": session.final_recommendation,
            "confidence": session.final_confidence,
            "minority_opinions": minority,
            "consensus_explanation": (
                f"Independent review reached {session.final_confidence:.0%} confidence."
            ),
        }
        await self._persist_deliberation(org_id, recommendation, result)
        return result

    async def _persist_deliberation(
        self,
        org_id: str,
        recommendation: str,
        payload: dict[str, Any],
    ) -> None:
        try:
            get_supabase_client(self.settings).table("intelligence_consensus_deliberations").insert(
                {
                    "org_id": org_id,
                    "recommendation_summary": str(payload.get("consensus_recommendation") or recommendation)[:2000],
                    "confidence": payload.get("confidence"),
                    "vote_breakdown": {},
                    "minority_opinions": payload.get("minority_opinions") or [],
                    "metadata": {
                        "source": "conversational_consensus_service",
                        "advisory_only": True,
                    },
                }
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.debug("chat consensus persist skipped org_id=%s error=%s", org_id, exc)


_conversational_consensus_service: ConversationalConsensusService | None = None


def get_conversational_consensus_service(settings: Settings | None = None) -> ConversationalConsensusService:
    global _conversational_consensus_service
    if _conversational_consensus_service is None or settings is not None:
        _conversational_consensus_service = ConversationalConsensusService(settings)
    return _conversational_consensus_service

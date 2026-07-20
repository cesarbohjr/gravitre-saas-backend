"""Structured multi-agent consensus for high-stakes recommendations."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.consensus_personas import (
    HIGH_STAKES_DEBATE_PERSONAS,
    build_agent_defs,
    persona_vote_weights,
)
from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_HEURISTIC,
    CONFIDENCE_SOURCE_MODEL,
    label_confidence,
)
from app.services.conversational_consensus_service import get_conversational_consensus_service
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

SCOPE_NOTE = (
    "ConsensusEngine produces advisory-only deliberation summaries. "
    "Humans approve via existing Approvals — no autonomous execution."
)


class ConsensusEngine:
    """
    Structured multi-agent consensus for high-stakes recommendations.
    Advisory_only — human still approves via existing Approvals.
    Does NOT replace SwarmOrchestrator sequential execution.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._chat_consensus = get_conversational_consensus_service(self.settings)

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def _get_agent_stance(
        self,
        org_id: str,
        persona_key: str,
        recommendation: str,
        context: dict,
    ) -> dict[str, Any]:
        stance_prompt = (
            f"Persona: {persona_key}. Evaluate this recommendation and respond JSON only: "
            '{"vote":"support|oppose|revise","confidence":0.0-1.0,"summary":"one sentence"}'
            f"\nRecommendation: {recommendation[:1200]}"
        )
        from app.services.model_router import TaskType, get_model_router

        router = get_model_router()
        used_fallback = False
        try:
            response = await router.complete(
                TaskType.DECISION_REASONING,
                prompt=stance_prompt,
                system_prompt="Return structured stance only — no chain-of-thought.",
                org_id=org_id,
                max_tokens=180,
                temperature=0.0,
            )
            raw = (response.content or "").strip()
            start = raw.find("{")
            end = raw.rfind("}")
            parsed = json.loads(raw[start : end + 1]) if start >= 0 and end > start else {}
        except Exception:  # noqa: BLE001
            used_fallback = True
            parsed = {"vote": "revise", "summary": "Unable to parse stance."}
        confidence = float(parsed.get("confidence") or 0.5)
        return {
            "persona": persona_key,
            "vote": str(parsed.get("vote") or "revise"),
            **label_confidence(
                confidence,
                source=CONFIDENCE_SOURCE_HEURISTIC if used_fallback else CONFIDENCE_SOURCE_MODEL,
                is_estimate=True,
            ),
            "summary": str(parsed.get("summary") or "")[:300],
        }

    def _aggregate_votes(
        self,
        stances: list[dict],
        vote_weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        weights = vote_weights or {}
        totals: dict[str, float] = {"support": 0.0, "oppose": 0.0, "revise": 0.0}
        confidences: list[float] = []
        for stance in stances:
            vote = str(stance.get("vote") or "revise")
            weight = float(weights.get(str(stance.get("persona") or ""), 1.0))
            totals[vote] = totals.get(vote, 0.0) + weight
            raw_conf = stance.get("confidence")
            confidences.append(float(raw_conf) if raw_conf is not None else 0.5)
        winner = max(totals.items(), key=lambda item: item[1])[0]
        tied = [k for k, v in totals.items() if v == totals[winner]]
        if len(tied) > 1:
            by_conf = {}
            for stance in stances:
                vote = str(stance.get("vote") or "revise")
                raw_conf = stance.get("confidence")
                by_conf[vote] = by_conf.get(vote, 0.0) + (
                    float(raw_conf) if raw_conf is not None else 0.5
                )
            winner = max(tied, key=lambda key: by_conf.get(key, 0.0))
        minority = [
            {
                "persona": s.get("persona"),
                "vote": s.get("vote"),
                "summary": s.get("summary"),
            }
            for s in stances
            if str(s.get("vote") or "") != winner
        ]
        aggregate_conf = (
            round(sum(confidences) / len(confidences), 4) if confidences else None
        )
        return {
            "consensus_vote": winner,
            "vote_breakdown": totals,
            **label_confidence(
                aggregate_conf,
                source=CONFIDENCE_SOURCE_HEURISTIC,
                is_estimate=True,
            ),
            "minority_opinions": minority,
        }

    async def _persist_deliberation(self, org_id: str, payload: dict[str, Any]) -> None:
        try:
            self._client().table("intelligence_consensus_deliberations").insert(
                {
                    "org_id": org_id,
                    "recommendation_summary": str(payload.get("consensus_recommendation") or "")[:2000],
                    "confidence": payload.get("confidence"),
                    "vote_breakdown": payload.get("vote_breakdown") or {},
                    "minority_opinions": payload.get("minority_opinions") or [],
                    "metadata": {
                        "risk_analysis": payload.get("risk_analysis"),
                        "source": "consensus_engine",
                        "personas": payload.get("personas") or [],
                        "advisory_only": True,
                    },
                }
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.debug("consensus persist skipped org_id=%s error=%s", org_id, exc)

    async def deliberate(
        self,
        org_id: str,
        recommendation: str,
        context: dict,
        agents: list[str],
    ) -> dict[str, Any]:
        personas = agents[:5] or list(HIGH_STAKES_DEBATE_PERSONAS)
        stances = [
            await self._get_agent_stance(org_id, persona, recommendation, context)
            for persona in personas
        ]
        aggregated = self._aggregate_votes(stances, persona_vote_weights(personas))
        council = await self._chat_consensus.deliberate(
            org_id,
            recommendation,
            context,
            personas,
        )
        consensus_text = str(council.get("consensus_recommendation") or recommendation)
        result = {
            "consensus_recommendation": consensus_text,
            "confidence": aggregated.get("confidence", council.get("confidence")),
            "vote_breakdown": aggregated.get("vote_breakdown") or {},
            "minority_opinions": aggregated.get("minority_opinions") or council.get("minority_opinions") or [],
            "risk_analysis": (
                "High-stakes recommendation reviewed by multiple advisory personas. "
                "Approval still required before any action."
            ),
            "consensus_explanation": str(council.get("consensus_explanation") or ""),
            "advisory_only": True,
            "approval_required": True,
            "scope_note": SCOPE_NOTE,
            "personas": personas,
        }
        await self._persist_deliberation(org_id, result)
        return result


_engine: ConsensusEngine | None = None


def get_consensus_engine(settings: Settings | None = None) -> ConsensusEngine:
    global _engine
    if _engine is None or settings is not None:
        _engine = ConsensusEngine(settings)
    return _engine

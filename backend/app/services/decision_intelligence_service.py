"""Decision intelligence — advisory recommendations from existing signals."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.services.answer_explanation import generate_suggestion_explanation
from app.services.knowledge_graph_service import get_knowledge_graph_service
from app.services.optimization_suggestion_service import get_optimization_suggestion_service
from app.services.outcome_attribution_service import get_outcome_attribution_service
from app.services.source_reliability_resolver import resolve_average_source_reliability
from app.workflows.repository import get_supabase_client


def _graph_recommendation_confidence(graph: dict[str, Any]) -> float:
    explanation = graph.get("explanation") if isinstance(graph.get("explanation"), dict) else {}
    related = explanation.get("relatedEntities") or []
    signals = explanation.get("businessSignals") or []
    if signals:
        return min(0.72, 0.5 + 0.04 * len(signals))
    if related:
        return min(0.65, 0.45 + 0.03 * len(related))
    return 0.45


class DecisionIntelligenceService:
    """
    Powers recommend / compare / plan capabilities.
    All outputs are advisory_only — no execution without Approvals.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def recommend_next_action(self, org_id: str, context: str) -> dict[str, Any]:
        graph = await get_knowledge_graph_service().answer_business_question(org_id, context)
        suggestions = await get_optimization_suggestion_service(self.settings).list_suggestions(
            org_id,
            status="pending_review",
            limit=10,
        )
        recommendations: list[dict[str, Any]] = []
        for row in suggestions.get("suggestions") or []:
            evidence = ["optimization_suggestions", row.get("suggestionType")]
            if graph.get("status") == "ok":
                entity = graph.get("identifiedEntity") or {}
                evidence.append(f"knowledge_graph:{entity.get('entityType')}:{entity.get('entityId')}")
            recommendations.append(
                {
                    "id": row.get("id"),
                    "action": row.get("title") or row.get("suggestionType"),
                    "reasoning": row.get("description") or row.get("rationale"),
                    "evidence_sources": evidence,
                    "confidence": float(row.get("confidence") or 0.55),
                    "requires_approval": True,
                    "estimated_impact": row.get("estimatedImpact"),
                }
            )

        if graph.get("status") == "ok":
            explanation = graph.get("explanation") if isinstance(graph.get("explanation"), dict) else {}
            entity = graph.get("identifiedEntity") or {}
            related = explanation.get("relatedEntities") or []
            signals = explanation.get("businessSignals") or []
            graph_confidence = _graph_recommendation_confidence(graph)
            if signals:
                for signal in signals[:3]:
                    recommendations.append(
                        {
                            "id": str(uuid4()),
                            "action": str(signal.get("title") or "Review graph-linked optimization signal"),
                            "reasoning": (
                                f"Knowledge graph linked pending signal for "
                                f"{entity.get('entityType')}:{entity.get('entityId')}."
                            ),
                            "evidence_sources": [
                                "knowledge_graph",
                                "optimization_suggestions",
                                signal.get("suggestion_type") or signal.get("suggestionType"),
                            ],
                            "confidence": graph_confidence,
                            "requires_approval": True,
                            "estimated_impact": signal.get("estimated_impact") or signal.get("estimatedImpact"),
                        }
                    )
            elif related:
                recommendations.append(
                    {
                        "id": str(uuid4()),
                        "action": f"Review {len(related)} related entities before acting on: {context[:120]}",
                        "reasoning": str(explanation.get("scopeNote") or graph.get("scopeNote") or ""),
                        "evidence_sources": [
                            "knowledge_graph",
                            f"{entity.get('entityType')}:{entity.get('entityId')}",
                        ],
                        "confidence": graph_confidence,
                        "requires_approval": True,
                        "estimated_impact": "Investigate related entities before acting",
                    }
                )
            elif not recommendations:
                recommendations.append(
                    {
                        "id": str(uuid4()),
                        "action": "Review identified entity context from knowledge graph",
                        "reasoning": "Graph entity resolved but no optimization suggestions yet.",
                        "evidence_sources": [
                            "knowledge_graph",
                            f"{entity.get('entityType')}:{entity.get('entityId')}",
                        ],
                        "confidence": graph_confidence,
                        "requires_approval": True,
                        "estimated_impact": "Investigate before acting",
                    }
                )

        source_rows = [{"type": "knowledge_graph"}] if graph.get("status") == "ok" else []
        source_reliability = await resolve_average_source_reliability(org_id, source_rows, self.settings)
        return {
            "recommendations": recommendations[:5],
            "advisory_only": True,
            "context": context,
            "graph_context": graph if graph.get("status") == "ok" else None,
            "source_reliability": source_reliability,
        }

    async def explain_recommendation(
        self,
        org_id: str,
        recommendation_id: str,
    ) -> dict[str, Any]:
        service = get_optimization_suggestion_service(self.settings)
        try:
            suggestion = await service.get_suggestion(org_id, recommendation_id)
        except ValueError:
            return {
                "status": "not_found",
                "recommendation_id": recommendation_id,
                "advisory_only": True,
            }
        explanation = generate_suggestion_explanation(suggestion)
        return {
            "status": "ok",
            "recommendation_id": recommendation_id,
            "explanation": explanation,
            "advisory_only": True,
        }

    async def compare_options(
        self,
        org_id: str,
        option_a: str,
        option_b: str,
        metric: str,
    ) -> dict[str, Any]:
        outcome_service = get_outcome_attribution_service(self.settings)
        snapshot = await outcome_service.load_admin_outcomes_snapshot(org_id, settings=self.settings)
        summaries = [
            row
            for row in snapshot.get("agentSummaries") or []
            if row.get("sufficientData")
        ]
        if not summaries:
            return {
                "status": "insufficient_data",
                "advisory_only": True,
                "uncertainty_disclosure": (
                    "Not enough v8 outcome measurements to compare options honestly."
                ),
                "optionA": option_a,
                "optionB": option_b,
                "metric": metric,
            }
        best = max(summaries, key=lambda row: float(row.get("winRate") or 0))
        return {
            "status": "ok",
            "advisory_only": True,
            "comparison": {
                "optionA": option_a,
                "optionB": option_b,
                "metric": metric,
                "bestObservedWinRate": best.get("winRate"),
                "sampleAgentId": best.get("agentId"),
                "sampleSize": best.get("sampleSize"),
            },
            "uncertainty_disclosure": "Comparison uses historical correlational outcomes only.",
        }

    async def scaffold_decision_plan(self, org_id: str, goal: str) -> dict[str, Any]:
        from app.services.handoff_service import get_agent

        client = self._client()
        agents = (
            client.table("agents")
            .select("id, name, role")
            .eq("org_id", org_id)
            .eq("status", "active")
            .limit(5)
            .execute()
            .data
            or []
        )
        planner_id = str(agents[0]["id"]) if agents else None
        if planner_id and not get_agent(client, org_id, planner_id):
            planner_id = None
        steps = [
            "Clarify success criteria and constraints",
            "Gather evidence from RAG and connectors",
            "Draft plan for human review",
            "Execute only after explicit approval",
        ]
        return {
            "status": "ok",
            "advisory_only": True,
            "goal": goal,
            "plannerAgentId": planner_id,
            "planSteps": steps,
            "requiresHumanReview": True,
            "message": "Plan scaffold only — not auto-executed.",
        }


_decision_intelligence_service: DecisionIntelligenceService | None = None


def get_decision_intelligence_service(settings: Settings | None = None) -> DecisionIntelligenceService:
    global _decision_intelligence_service
    if _decision_intelligence_service is None or settings is not None:
        _decision_intelligence_service = DecisionIntelligenceService(settings)
    return _decision_intelligence_service

"""Central coordinator for the Gravitre Intelligence Engine 10-stage pipeline."""
from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.correlational_causal_context import load_causal_enrichment_context
from app.services.source_reliability_resolver import resolve_average_source_reliability
from app.services.agent_selector import get_agent_selector
from app.services.ai_trust_layer import get_ai_trust_layer
from app.services.chat_dialogue_settings import load_chat_dialogue_settings
from app.services.clarification_engine import get_clarification_engine
from app.services.confidence_scorer import get_confidence_scorer
from app.services.context_assembler import get_context_assembler
from app.services.contextual_understanding_service import get_contextual_understanding_service
from app.services.conversational_consensus_service import get_conversational_consensus_service
from app.services.decision_intelligence_service import get_decision_intelligence_service
from app.services.dialogue_policy_engine import get_dialogue_policy_engine
from app.services.explanation_generator import get_explanation_generator
from app.services.knowledge_graph_service import get_knowledge_graph_service
from app.services.learning_strategy_keys import build_route_strategy_key, parse_segment_key
from app.services.model_router import get_model_router
from app.services.model_selector import get_model_selector
from app.services.optimization_suggestion_service import get_optimization_suggestion_service
from app.services.outcome_tracker import get_outcome_tracker
from app.services.proactive_guidance_service import get_proactive_guidance_service
from app.services.risk_approval_evaluator import get_risk_approval_evaluator
from app.services.sentiment_friction_service import get_sentiment_friction_service
from app.services.task_classifier import get_task_classifier
from app.services.tool_connector_selector import get_tool_connector_selector

logger = get_logger(__name__)


class IntelligenceRouter:
    """
    Routes requests through named pipeline stages.
    Stages 1-7 always considered; 8-10 only when classification requires action.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._task_classifier = get_task_classifier(self.settings)
        self._context_assembler = get_context_assembler(self.settings)
        self._model_selector = get_model_selector(self.settings)
        self._agent_selector = get_agent_selector(self.settings)
        self._tool_selector = get_tool_connector_selector(self.settings)
        self._risk_evaluator = get_risk_approval_evaluator(self.settings)
        self._outcome_tracker = get_outcome_tracker(self.settings)
        self._understanding = get_contextual_understanding_service(self.settings)
        self._clarification = get_clarification_engine(self.settings)
        self._sentiment = get_sentiment_friction_service()
        self._consensus = get_conversational_consensus_service(self.settings)
        self._guidance = get_proactive_guidance_service(self.settings)

    async def route(
        self,
        org_id: str,
        user_id: str,
        request: str,
        surface: str = "api",
        mode: str = "standard",
        conversation_history: list[dict] | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        dialogue_settings = await load_chat_dialogue_settings(org_id, self.settings)
        sentiment = (
            self._sentiment.analyze(request, conversation_history or [])
            if dialogue_settings.get("sentiment_detection_enabled", True)
            else {"recommended_adaptation": "none", "frustration_score": 0.0}
        )

        understanding = await self._understanding.understand(
            request,
            conversation_history,
            org_id,
        )
        classification = await self._task_classifier.classify(
            org_id,
            request,
            conversation_history,
            understanding=understanding,
        )
        from app.services.knowledge_intelligence_service import enrich_classification_with_query_cluster

        classification = await enrich_classification_with_query_cluster(
            classification,
            org_id,
            request,
            self.settings,
        )
        confidence = float(classification.get("classification_confidence") or 0.55)

        clarification = await self._clarification.should_clarify(
            classification,
            {},
            conversation_history,
            conversation_id=conversation_id,
            org_id=org_id,
            understanding=understanding,
        )
        if clarification["should_clarify"]:
            wrapped = get_ai_trust_layer().wrap_response(
                answer=clarification["question"] or "Could you clarify?",
                sources=[],
                confidence=confidence,
                reasoning_summary=f"Clarification needed: {clarification['reason']}",
                actions_taken=[],
                actions_pending_approval=[],
                advisory_only=True,
            )
            wrapped["dialogue_mode"] = "clarify"
            return wrapped

        context = await self._context_assembler.assemble(org_id, user_id, request, classification)
        context["connected_integrations"] = context.get("connected_integrations") or []

        risk_evaluation: dict[str, Any] = {"requires_approval": False, "can_proceed_without_approval": True}
        if classification.get("requires_action"):
            action = {"type": classification.get("intent"), "estimated_impact": "medium", "is_destructive": False}
            risk_evaluation = await self._risk_evaluator.evaluate(
                org_id,
                user_id,
                action,
                classification,
                {},
            )

        policy = get_dialogue_policy_engine(
            clarification_threshold=float(dialogue_settings.get("clarification_threshold") or 0.65),
            escalation_threshold=float(dialogue_settings.get("escalation_threshold") or 0.40),
        ).select_mode(
            classification,
            clarification,
            sentiment,
            risk_evaluation,
            confidence,
            conversation_history,
        )

        if policy["mode"] == "clarify":
            wrapped = get_ai_trust_layer().wrap_response(
                answer=clarification.get("question") or policy["next_move"],
                sources=[],
                confidence=confidence,
                reasoning_summary=policy["reason"],
                actions_taken=[],
                actions_pending_approval=[],
                advisory_only=True,
            )
            wrapped["dialogue_mode"] = "clarify"
            return wrapped

        model_selection = await self._model_selector.select(org_id, classification)
        enrichments = await self._run_enrichments(org_id, request, classification, context)
        if (context.get("external_context") or {}).get("findings"):
            enrichments = {**enrichments, "web": context["external_context"]}
        strategy_key = build_route_strategy_key(model_selection, classification, enrichments)
        segment_key = parse_segment_key(classification)

        if classification.get("requires_action"):
            result = await self._route_to_execution(
                org_id,
                user_id,
                request,
                classification,
                context,
                enrichments,
                model_selection,
                surface,
                strategy_key=strategy_key,
                segment_key=segment_key,
            )
        else:
            result = await self._route_to_knowledge_response(
                org_id,
                user_id,
                request,
                classification,
                context,
                enrichments,
                model_selection,
                surface,
                strategy_key=strategy_key,
                segment_key=segment_key,
            )

        result["strategy_key"] = strategy_key
        result["segment_key"] = segment_key

        from app.services.domain_routing_policy import build_routing_metadata

        result["domain"] = classification.get("domain") or understanding.get("domain")
        result["domain_routing"] = build_routing_metadata(classification)
        result["retrieval_plan"] = context.get("retrieval_plan") or {}
        result["retrieval_effectiveness"] = context.get("retrieval_effectiveness") or {}

        result["dialogue_mode"] = policy["mode"]
        result["sentiment"] = sentiment
        result["understanding"] = understanding

        primary_answer = str(result.get("answer") or "")
        if primary_answer and policy["mode"] in {"guide", "recommend", "answer"}:
            router = get_model_router()
            task_complexity = str(classification.get("complexity") or "medium")
            if router.should_trigger_agent_debate(float(result.get("confidence") or confidence), task_complexity):
                from app.operators.consensus_engine import get_consensus_engine
                from app.services.consensus_personas import HIGH_STAKES_DEBATE_PERSONAS

                debate = await get_consensus_engine(self.settings).deliberate(
                    org_id,
                    primary_answer,
                    {"request": request, "classification": classification},
                    list(HIGH_STAKES_DEBATE_PERSONAS),
                )
                result["answer"] = str(debate.get("consensus_recommendation") or primary_answer)
                result["consensus_used"] = True
                result["consensus_mode"] = "high_stakes_debate"
                result["vote_breakdown"] = debate.get("vote_breakdown")
                result["minority_opinions"] = debate.get("minority_opinions")
            else:
                refined = await self._consensus.refine_if_warranted(
                    org_id,
                    request,
                    primary_answer,
                    classification,
                    float(result.get("confidence") or confidence),
                    policy["mode"],
                )
                if refined.get("consensus_used"):
                    result["answer"] = refined["response"]
                    result["consensus_used"] = True
                    result["consensus_mode"] = "chat_refinement"
                    result["minority_opinions"] = refined.get("minority_opinions") or []

        suggestions = await self._guidance.get_suggestions(
            org_id,
            user_id,
            conversation_id,
            classification,
            policy["mode"],
            str(result.get("answer") or ""),
            connected_integrations=context.get("connected_integrations") or [],
        )
        result["proactive_suggestions"] = suggestions
        from app.services.intelligence_visibility_service import get_intelligence_visibility_service

        visibility = get_intelligence_visibility_service(self.settings)
        if visibility.is_enabled():
            result["decision_transparency"] = await visibility.build_decision_envelope_from_response(
                org_id,
                result,
                classification,
                context,
                decision_type=str(policy.get("mode") or "answer"),
            )
        return result

    async def _run_enrichments(
        self,
        org_id: str,
        request: str,
        classification: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        tasks: dict[str, Any] = {}
        if classification.get("requires_prediction"):
            tasks["prediction"] = self._get_predictions(org_id, classification)
        if classification.get("requires_causal"):
            tasks["causal"] = self._get_causal_analysis(org_id, request)
        if classification.get("requires_graph") and not context.get("graph_context"):
            entity_type = classification.get("entity_type") or "unknown"
            entity_id = classification.get("entity_id") or "unknown"
            if entity_type != "unknown" and entity_id != "unknown":
                tasks["graph"] = get_knowledge_graph_service().explain_entity(
                    org_id,
                    str(entity_type),
                    str(entity_id),
                )
        if not tasks:
            return {}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return {
            key: value
            for key, value in zip(tasks.keys(), results)
            if not isinstance(value, Exception)
        }

    async def _get_predictions(self, org_id: str, classification: dict[str, Any]) -> dict[str, Any]:
        selection = await self._model_selector.select(org_id, classification)
        if selection.get("primary_model") == "ml_internal":
            return {
                "status": "ml_available",
                "model": selection.get("ml_model_name"),
                "note": "Use InferenceService at execution time with org-trained artifact.",
            }
        return {
            "status": "llm_fallback",
            "reason": selection.get("reason"),
            "confidence_note": "No trained internal ML model — forecast uses correlational signals only.",
        }

    async def _get_causal_analysis(self, org_id: str, request: str) -> dict[str, Any]:
        return await load_causal_enrichment_context(org_id, request, self.settings)

    async def _route_to_knowledge_response(
        self,
        org_id: str,
        user_id: str,
        request: str,
        classification: dict[str, Any],
        context: dict[str, Any],
        enrichments: dict[str, Any],
        model_selection: dict[str, Any],
        surface: str,
        *,
        strategy_key: str | None = None,
        segment_key: str = "default",
    ) -> dict[str, Any]:
        _ = user_id
        recommendations = await get_decision_intelligence_service(self.settings).recommend_next_action(
            org_id,
            request,
        )
        primary = (recommendations.get("recommendations") or [{}])[0]
        sources = list(context.get("rag_context") or [])
        if context.get("graph_context"):
            sources.append({"type": "knowledge_graph", "context": context["graph_context"]})
        external = context.get("external_context") or {}
        for finding in external.get("findings") or []:
            if not isinstance(finding, dict):
                continue
            sources.append(
                {
                    "type": "web",
                    "content": finding.get("summary"),
                    "url": finding.get("source"),
                    "source_credibility": finding.get("source_credibility"),
                }
            )
        if enrichments.get("prediction"):
            sources.append({"type": "prediction", "data": enrichments["prediction"]})

        rag_scores = [
            float(row.get("score") or 0.0)
            for row in sources
            if isinstance(row.get("score"), (int, float))
        ]
        rag_quality = sum(rag_scores) / len(rag_scores) if rag_scores else None
        source_reliability = await resolve_average_source_reliability(org_id, sources, self.settings)
        confidence = get_confidence_scorer().compute_with_calibration(
            org_id,
            surface=surface,
            rag_quality=rag_quality,
            source_reliability=source_reliability,
            ml_confidence=0.7 if model_selection.get("primary_model") == "ml_internal" else None,
            classification_confidence=classification.get("classification_confidence"),
        )
        explanation = await get_explanation_generator().explain(
            "answer",
            org_id,
            sources,
            {"refined_query": request},
            classification,
        )
        if enrichments.get("causal", {}).get("status") == "not_available":
            explanation = f"{explanation} Causal analysis is PLANNED — correlational signals only."
        elif enrichments.get("causal", {}).get("status") == "correlational_fallback":
            note = enrichments["causal"].get("confidence_note") or "Correlational only — not causal proof."
            explanation = f"{explanation} {note}"
        if external.get("findings"):
            explanation = (
                f"{explanation} External web sources were included where org knowledge was insufficient."
            )

        trust_layer = get_ai_trust_layer()
        freshness_label, stale_warnings, freshness_envelope = trust_layer.build_knowledge_freshness_envelope(
            context.get("retrieval_plan"),
        )
        confidence = trust_layer.apply_freshness_to_confidence(
            confidence,
            stale_source_warnings=stale_warnings,
            freshness_penalty=min(0.15, 0.03 * len(stale_warnings)) if stale_warnings else 0.0,
        )

        answer = str(primary.get("action") or self._summarize_context(context, request))
        wrapped = trust_layer.wrap_response(
            answer=answer,
            sources=sources,
            confidence=confidence,
            reasoning_summary=explanation,
            actions_taken=[],
            actions_pending_approval=primary if primary.get("requires_approval", True) else [],
            advisory_only=True,
            data_freshness=freshness_label,
            stale_source_warnings=stale_warnings,
            knowledge_freshness=freshness_envelope,
        )
        wrapped["classification"] = classification
        wrapped["model_selection"] = model_selection
        wrapped["enrichments"] = enrichments
        wrapped["surface"] = surface
        wrapped["strategy_key"] = strategy_key
        self._outcome_tracker.track(
            org_id,
            None,
            None,
            None,
            wrapped,
            classification,
        )
        return wrapped

    async def _route_to_execution(
        self,
        org_id: str,
        user_id: str,
        request: str,
        classification: dict[str, Any],
        context: dict[str, Any],
        enrichments: dict[str, Any],
        model_selection: dict[str, Any],
        surface: str,
        *,
        strategy_key: str | None = None,
        segment_key: str = "default",
    ) -> dict[str, Any]:
        agent_selection = await self._agent_selector.select(org_id, classification)
        tool_selection = await self._tool_selector.select_for_task(
            org_id,
            classification,
            agent_selection.get("persona") or {},
        )
        action = {
            "type": classification.get("intent"),
            "estimated_impact": "medium",
            "is_destructive": False,
        }
        risk_level = str(classification.get("risk_level") or "low")
        simulation_summary = None
        if risk_level != "low":
            from app.services.simulation_service import get_simulation_service

            simulation_summary = await get_simulation_service(self.settings).simulate_action(
                org_id,
                str(action.get("type") or "connector_write_action"),
                {"workflow_id": classification.get("entity_id"), "connector_id": None},
            )
        risk = await self._risk_evaluator.evaluate(
            org_id,
            user_id,
            action,
            classification,
            agent_selection.get("persona") or {},
            simulation_summary=simulation_summary,
        )
        explanation = await get_explanation_generator().explain(
            "decision",
            org_id,
            context.get("rag_context") or [],
            {"plan": request, "risk": risk},
            classification,
        )
        confidence = get_confidence_scorer().compute_with_calibration(
            org_id,
            surface=surface,
            rag_quality=None,
            source_reliability=None,
            ml_confidence=None,
            classification_confidence=classification.get("classification_confidence"),
        )
        wrapped = get_ai_trust_layer().wrap_response(
            answer="Execution requires approval before any write action proceeds.",
            sources=context.get("rag_context") or [],
            confidence=confidence,
            reasoning_summary=explanation,
            actions_taken=[],
            actions_pending_approval=[action],
            advisory_only=not risk.get("can_proceed_without_approval"),
            simulation_summary=simulation_summary,
            action_safety_level=risk_level,
            routing_summary=str(classification.get("intent")),
        )
        wrapped["simulation_summary"] = simulation_summary
        wrapped["classification"] = classification
        wrapped["agent_selection"] = agent_selection
        wrapped["tool_selection"] = tool_selection
        wrapped["risk_evaluation"] = risk
        wrapped["model_selection"] = model_selection
        wrapped["enrichments"] = enrichments
        wrapped["requires_approval"] = True
        wrapped["surface"] = surface
        wrapped["strategy_key"] = strategy_key
        return wrapped

    @staticmethod
    def _summarize_context(context: dict[str, Any], request: str) -> str:
        rag = context.get("rag_context") or []
        if rag:
            return (
                f"Based on {len(rag)} retrieved source(s), review the evidence for: {request}. "
                "No automated action was taken."
            )
        return (
            f"Insufficient org knowledge matched '{request}'. "
            "Connect more sources or run company intelligence to improve answers."
        )

    async def forecast(
        self,
        org_id: str,
        metric: str,
        horizon_days: int = 30,
    ) -> dict[str, Any]:
        classification = await self._task_classifier.classify(org_id, f"forecast {metric}")
        classification["requires_prediction"] = True
        selection = await self._model_selector.select(org_id, classification)
        prediction = await self._get_predictions(org_id, classification)
        confidence_note = prediction.get("confidence_note") or (
            "Forecast uses historical correlational data — not causal proof."
        )
        explanation = await get_explanation_generator().explain(
            "prediction",
            org_id,
            [],
            {
                "data_points_used": horizon_days,
                "model_used": selection.get("ml_model_name") or selection.get("llm_tier"),
                "confidence_note": confidence_note,
            },
        )
        confidence = get_confidence_scorer().compute_with_calibration(
            org_id,
            surface="forecast",
            rag_quality=None,
            source_reliability=0.5,
            ml_confidence=0.65 if selection.get("primary_model") == "ml_internal" else 0.45,
            classification_confidence=classification.get("classification_confidence"),
        )
        return get_ai_trust_layer().wrap_response(
            answer=f"Forecast for {metric} over {horizon_days} days is advisory only.",
            sources=[{"type": "prediction", "metric": metric, "selection": selection}],
            confidence=confidence,
            reasoning_summary=explanation,
            actions_taken=[],
            actions_pending_approval=[],
            advisory_only=True,
        )

    async def optimize(self, org_id: str, workflow_id: str | None = None) -> dict[str, Any]:
        service = get_optimization_suggestion_service(self.settings)
        suggestions = await service.list_suggestions(org_id, status="pending_review", limit=20)
        if workflow_id:
            suggestions["suggestions"] = [
                row
                for row in suggestions.get("suggestions") or []
                if workflow_id in str(row.get("evidence") or row.get("title") or "")
            ]
        return {
            "advisory_only": True,
            "workflow_id": workflow_id,
            "suggestions": suggestions.get("suggestions") or [],
            "note": "Human-gated v10 optimization — never auto-applies except slow_step preview.",
        }


_intelligence_router: IntelligenceRouter | None = None


def get_intelligence_router(settings: Settings | None = None) -> IntelligenceRouter:
    global _intelligence_router
    if _intelligence_router is None or settings is not None:
        _intelligence_router = IntelligenceRouter(settings)
    return _intelligence_router

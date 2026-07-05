"""Single coordinator for post-response outcome recording."""
from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.learning_strategy_keys import build_route_strategy_key, parse_segment_key

logger = get_logger(__name__)


class IntelligenceOutcomeCoordinator:
    """
    Unifies outcome_learning, learning_feedback, and strategy ledger hooks.
    OutcomeTracker and intelligence_engine routers should call this — not subsystems directly.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def record_response_async(
        self,
        org_id: str,
        *,
        agent_id: str | None,
        message_id: str | None,
        action_taken: dict[str, Any] | None,
        response: dict[str, Any],
        classification: dict[str, Any],
    ) -> None:
        asyncio.create_task(
            self.record_response(
                org_id,
                agent_id=agent_id,
                message_id=message_id,
                action_taken=action_taken,
                response=response,
                classification=classification,
            )
        )

    async def record_response(
        self,
        org_id: str,
        *,
        agent_id: str | None,
        message_id: str | None,
        action_taken: dict[str, Any] | None,
        response: dict[str, Any],
        classification: dict[str, Any],
    ) -> None:
        from app.services.platform_intelligence_dedup import build_intelligence_dedup_key, should_skip_duplicate_event

        dedup_key = build_intelligence_dedup_key(
            org_id,
            "assistant_response",
            "message",
            str(message_id or response.get("id") or "unknown"),
            str(classification.get("intent") or "response"),
        )
        if should_skip_duplicate_event(dedup_key):
            return
        try:
            if action_taken and action_taken.get("metric_before") is not None:
                from app.services.outcome_attribution_service import get_outcome_attribution_service

                await get_outcome_attribution_service(self.settings).record_action_baseline(
                    org_id=org_id,
                    agent_id=agent_id,
                    workflow_run_id=action_taken.get("workflow_run_id"),
                    action_type=str(action_taken.get("type") or action_taken.get("action_type") or "unknown"),
                    target_entity_type=str(action_taken.get("entity_type") or "unknown"),
                    target_entity_id=str(action_taken.get("entity_id") or "unknown"),
                    metric_name=str(action_taken.get("metric_name") or "custom_metric"),
                    metric_value_before=action_taken.get("metric_before"),
                )

            strategy_key = response.get("strategy_key") or build_route_strategy_key(
                response.get("model_selection"),
                classification,
                response.get("enrichments"),
            )
            segment_key = response.get("segment_key") or parse_segment_key(classification)

            if message_id:
                from app.services.response_evaluation_service import consolidate_recent

                await consolidate_recent(self.settings, org_id, since_days=1)

            from app.services.learning_feedback_loop import get_learning_feedback_loop

            await get_learning_feedback_loop(self.settings).process_feedback(
                org_id,
                "response_quality" if message_id else "action_outcome",
                {
                    "message_id": message_id,
                    "response": response,
                    "classification": classification,
                    "action_taken": action_taken,
                    "agent_id": agent_id,
                    "strategy_key": strategy_key,
                    "segment_key": segment_key,
                    "domain": classification.get("domain"),
                    "retrieval_effectiveness": response.get("retrieval_effectiveness")
                    or classification.get("retrieval_effectiveness"),
                },
            )

            from app.services.outcome_learning_service import get_outcome_learning_service

            learning = get_outcome_learning_service(self.settings)
            domain = classification.get("domain") or {}
            if message_id:
                learning.record_recommendation_outcome_async(
                    org_id=org_id,
                    recommendation_id=message_id,
                    outcome_event="recommendation_created",
                    department=domain.get("department_key") or classification.get("department"),
                    task_type=classification.get("intent"),
                    confidence_score=response.get("confidence"),
                    model_name=(response.get("model_selection") or {}).get("ml_model_name"),
                    strategy_key=strategy_key,
                    domain_context=domain,
                    retrieval_effectiveness=response.get("retrieval_effectiveness")
                    or classification.get("retrieval_effectiveness"),
                )

            if response.get("consensus_used"):
                from app.services.strategy_performance_ledger import get_strategy_performance_ledger

                await get_strategy_performance_ledger(self.settings).record(
                    org_id,
                    f"consensus:{response.get('consensus_mode') or 'debate'}",
                    "neutral",
                    strategy_family="consensus",
                    segment_key=str(segment_key),
                    metadata={
                        "strategy_key": strategy_key,
                        "minority_opinion_count": len(response.get("minority_opinions") or []),
                    },
                )

            from app.services.adaptive_learning_service import get_adaptive_learning_service

            adaptive = get_adaptive_learning_service(self.settings)
            if adaptive.is_enabled():
                await adaptive.ingest_response_outcome(
                    org_id,
                    segment_key=str(segment_key),
                    classification=classification,
                    response=response,
                    metadata={
                        "retrieval_effectiveness": response.get("retrieval_effectiveness")
                        or classification.get("retrieval_effectiveness"),
                        "strategy_key": strategy_key,
                    },
                )

            from app.services.meta_learning_service import get_meta_learning_service

            meta = get_meta_learning_service(self.settings)
            if meta.is_enabled():
                polarity = "positive" if float((response.get("confidence") or 0)) >= 0.65 else "neutral"
                retrieval = response.get("retrieval_effectiveness") or classification.get("retrieval_effectiveness") or {}
                if isinstance(retrieval, dict):
                    score = retrieval.get("retrieval_score")
                    if score is not None:
                        polarity = "positive" if float(score) >= 0.75 else "negative" if float(score) <= 0.35 else polarity
                model_selection = response.get("model_selection") or {}
                if model_selection.get("primary_model") == "ml_internal" and model_selection.get("ml_model_name"):
                    model_key = f"model:{model_selection['ml_model_name']}"
                else:
                    model_key = f"llm:{model_selection.get('llm_tier') or 'standard'}"
                await meta.record_strategy_outcome(
                    org_id,
                    str(segment_key),
                    "model",
                    model_key,
                    polarity,
                    metadata={"strategy_key": strategy_key},
                )
                agent_selection = response.get("agent_selection") or {}
                persona_key = agent_selection.get("persona_key") or (agent_selection.get("persona") or {}).get("key")
                if persona_key:
                    await meta.record_strategy_outcome(
                        org_id,
                        str(segment_key),
                        "agent",
                        meta.build_agent_strategy_key(str(persona_key)),
                        polarity,
                        metadata={"strategy_key": strategy_key},
                    )
                if strategy_key:
                    await meta.record_strategy_outcome(
                        org_id,
                        str(segment_key),
                        "retrieval",
                        meta.build_retrieval_strategy_key(str(strategy_key)),
                        polarity,
                        metadata={"retrieval_effectiveness": retrieval},
                    )
                connectors = (agent_selection.get("persona") or {}).get("preferred_connectors") or []
                if connectors:
                    await meta.record_strategy_outcome(
                        org_id,
                        str(segment_key),
                        "connector_combo",
                        meta.build_connector_combo_key(list(connectors)),
                        polarity,
                    )
        except Exception as exc:  # noqa: BLE001
            logger.debug("intelligence_outcome_coordinator_skipped org_id=%s error=%s", org_id, exc)


_coordinator: IntelligenceOutcomeCoordinator | None = None


def get_intelligence_outcome_coordinator(settings: Settings | None = None) -> IntelligenceOutcomeCoordinator:
    global _coordinator
    if _coordinator is None or settings is not None:
        _coordinator = IntelligenceOutcomeCoordinator(settings)
    return _coordinator

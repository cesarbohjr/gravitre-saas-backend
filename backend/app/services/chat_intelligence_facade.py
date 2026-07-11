"""Thin facade — shared IntelligenceRouter stages for live AI chat (no duplicate pipeline)."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.services.ai_trust_layer import get_ai_trust_layer
from app.services.intelligence_router import IntelligenceRouter
from app.services.knowledge_intelligence_service import enrich_classification_with_query_cluster
from app.services.learning_strategy_keys import build_route_strategy_key, parse_segment_key
from app.services.model_selector import get_model_selector

_facade: "ChatIntelligenceFacade | None" = None


class ChatIntelligenceFacade:
    """
    Delegates post-classification intelligence stages to IntelligenceRouter helpers.
    Keeps AgentIntelligence as the single chat execution core.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._router = IntelligenceRouter(self.settings)

    async def enrich_classification(
        self,
        classification: dict[str, Any],
        org_id: str,
        query_text: str,
    ) -> dict[str, Any]:
        return await enrich_classification_with_query_cluster(
            classification,
            org_id,
            query_text,
            self.settings,
        )

    async def run_router_enrichments(
        self,
        org_id: str,
        request: str,
        classification: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._router._run_enrichments(  # noqa: SLF001
            org_id,
            request,
            classification,
            context or {},
        )

    async def simulate_action_if_required(
        self,
        org_id: str,
        user_id: str,
        classification: dict[str, Any],
        *,
        action: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not classification.get("requires_action"):
            return None
        from app.services.simulation_service import get_simulation_service

        payload = action or {
            "type": classification.get("intent") or "unknown",
            "estimated_impact": "medium",
            "is_destructive": False,
        }
        action_type = str(payload.get("type") or classification.get("intent") or "unknown")
        try:
            return await get_simulation_service(self.settings).simulate_action(
                org_id,
                action_type,
                dict(payload),
            )
        except Exception:  # noqa: BLE001
            return None

    def build_trust_metadata(
        self,
        *,
        answer: str,
        sources: list[dict[str, Any]],
        confidence: float,
        reasoning_summary: str,
        actions_taken: list[dict[str, Any]] | None = None,
        actions_pending_approval: list[dict[str, Any]] | None = None,
        advisory_only: bool = False,
    ) -> dict[str, Any]:
        wrapped = get_ai_trust_layer().wrap_response(
            answer=answer,
            sources=sources,
            confidence=confidence,
            reasoning_summary=reasoning_summary,
            actions_taken=actions_taken or [],
            actions_pending_approval=actions_pending_approval or [],
            advisory_only=advisory_only,
        )
        return {
            "trust_envelope": {
                "confidence": wrapped.get("confidence"),
                "reasoning_summary": wrapped.get("reasoning_summary"),
                "advisory_only": wrapped.get("advisory_only"),
                "actions_taken": wrapped.get("actions_taken"),
                "actions_pending_approval": wrapped.get("actions_pending_approval"),
            }
        }

    def build_route_metadata(
        self,
        classification: dict[str, Any],
        model_selection: dict[str, Any] | None,
        enrichments: dict[str, Any] | None,
    ) -> dict[str, Any]:
        segment_key = parse_segment_key(classification)
        return {
            "strategy_key": build_route_strategy_key(model_selection, classification, enrichments),
            "segment_key": segment_key,
            "model_selection": model_selection or {},
        }

    async def resolve_chat_model(
        self,
        org_id: str,
        agent: dict[str, Any],
        client: Any,
        task_text: str,
        classification: dict[str, Any],
        *,
        model_override: str | None = None,
        mode: str | None = None,
        connected_integrations: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        from app.operators.agent_intelligence import MODEL_TIERS, resolve_agent_inference_model
        from app.services.assistant_turn_complexity import (
            classify_assistant_turn_complexity,
            model_tier_for_task_type,
        )

        if model_override:
            return model_override, {"source": "override"}
        inference = resolve_agent_inference_model(client, org_id, agent)
        if inference.fine_tuned_openai_id:
            return inference.fine_tuned_openai_id, {"source": "fine_tuned"}
        configured = (agent.get("model") or inference.base_model or "").strip()
        if configured:
            return configured, {"source": "agent_configured"}

        task_type = classify_assistant_turn_complexity(
            task_text,
            mode=mode
            or str(classification.get("mode") or classification.get("intelligence_mode") or ""),
            connected_integrations=connected_integrations,
            parameters={
                "complexity": classification.get("complexity"),
                "require_high_model": classification.get("require_high_model"),
            },
        )
        complexity_tier = model_tier_for_task_type(task_type)

        selection = await get_model_selector(self.settings).select(org_id, classification)
        llm_model = str(selection.get("llm_model") or "").strip()
        if llm_model:
            return llm_model, {
                "source": "model_selector",
                "task_type": task_type.value,
                "complexity_tier": complexity_tier,
                **selection,
            }
        return MODEL_TIERS[complexity_tier]["openai"], {
            "source": "turn_complexity",
            "task_type": task_type.value,
            "tier": complexity_tier,
            **selection,
        }


def get_chat_intelligence_facade(settings: Settings | None = None) -> ChatIntelligenceFacade:
    global _facade
    if _facade is None or settings is not None:
        _facade = ChatIntelligenceFacade(settings)
    return _facade

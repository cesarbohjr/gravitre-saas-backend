"""Operational Intelligence Layer — compound what / why / action / outcome.

Safe facade over existing Gravitre services. Fail-open on every hook so chat
and workflows never break if a sub-component errors.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.services.context_distiller import distill_context_sources
from app.services.operational_intelligence_patterns import (
    list_patterns,
    pattern_coverage_summary,
)
from app.services.predictive_context_loader import adjust_registry_plan_for_prediction
from app.services.reflection_loop_service import get_reflection_loop_service
from app.services.self_healing_advisor import advise_self_heal
from app.services.working_memory_profile import (
    WorkingMemoryProfile,
    build_working_memory_profile,
)

logger = get_logger(__name__)


class OperationalIntelligenceLayer:
    """
    Cross-cutting operational intelligence hooks used by IntelligenceOrchestrator
    and post-delivery paths. Does not replace AgentIntelligence or workflow engines.
    """

    def predict_context_plan(self, plan: Any, *, classification: dict[str, Any], query: str = "") -> Any:
        try:
            return adjust_registry_plan_for_prediction(plan, classification=classification, query=query)
        except Exception as exc:  # noqa: BLE001
            logger.debug("oil predictive context skipped error=%s", exc)
            return plan

    def build_working_memory(
        self,
        *,
        conversation_memory: dict[str, Any] | None,
        task_state: dict[str, Any] | None,
        session_state: dict[str, Any] | None = None,
        org_context_block: str = "",
        query: str = "",
    ) -> WorkingMemoryProfile:
        try:
            return build_working_memory_profile(
                conversation_memory=conversation_memory,
                task_state=task_state,
                session_state=session_state,
                org_context_block=org_context_block,
                query=query,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("oil working memory skipped error=%s", exc)
            return WorkingMemoryProfile()

    def distill_sources(self, sources: list[Any], *, per_source_max: int = 1800) -> tuple[list[Any], dict[str, Any]]:
        try:
            return distill_context_sources(sources, per_source_max=per_source_max)
        except Exception as exc:  # noqa: BLE001
            logger.debug("oil distillation skipped error=%s", exc)
            return sources, {"distilledSourceCount": 0, "error": str(exc)}

    def reflect(
        self,
        *,
        critic: dict[str, Any] | None,
        confidence: dict[str, Any] | None,
        tool_results: list[dict[str, Any]] | None = None,
        strategic_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return get_reflection_loop_service().evaluate(
                critic=critic,
                confidence=confidence,
                tool_results=tool_results,
                strategic_plan=strategic_plan,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("oil reflection skipped error=%s", exc)
            return {"phase": "deliver", "should_revise": False, "should_deliver": True, "error": str(exc)}

    def heal_suggestions(
        self,
        *,
        tool_results: list[dict[str, Any]] | None,
        connected_integrations: list[str] | None = None,
        action: str | None = None,
    ) -> dict[str, Any]:
        try:
            return advise_self_heal(
                tool_results=tool_results,
                connected_integrations=connected_integrations,
                action=action,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("oil self-heal skipped error=%s", exc)
            return {"hasFailures": False, "suggestions": [], "advisoryOnly": True, "error": str(exc)}

    def build_operational_envelope(
        self,
        *,
        what_happened: str | None = None,
        why: str | None = None,
        action: dict[str, Any] | list[Any] | None = None,
        outcome: dict[str, Any] | None = None,
        confidence: dict[str, Any] | None = None,
        reflection: dict[str, Any] | None = None,
        heal: dict[str, Any] | None = None,
        working_memory: WorkingMemoryProfile | dict[str, Any] | None = None,
        patterns_invoked: list[str] | None = None,
    ) -> dict[str, Any]:
        """Compound learning surface: what / why / action / outcome."""
        wm = working_memory.to_dict() if isinstance(working_memory, WorkingMemoryProfile) else (working_memory or {})
        return {
            "whatHappened": what_happened,
            "why": why,
            "action": action,
            "outcome": outcome or {},
            "confidence": confidence or {},
            "reflection": reflection or {},
            "selfHeal": heal or {},
            "workingMemory": wm,
            "patternsInvoked": patterns_invoked or [],
            "coverage": pattern_coverage_summary(),
        }

    def catalog(self) -> dict[str, Any]:
        return {
            "patterns": list_patterns(),
            "coverage": pattern_coverage_summary(),
        }


_oil: OperationalIntelligenceLayer | None = None


def get_operational_intelligence_layer() -> OperationalIntelligenceLayer:
    global _oil
    if _oil is None:
        _oil = OperationalIntelligenceLayer()
    return _oil

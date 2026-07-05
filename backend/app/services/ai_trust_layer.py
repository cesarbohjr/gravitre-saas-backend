"""Unified trust envelope over existing v2/v7 explanation and audit signals."""
from __future__ import annotations

from typing import Any


class AITrustLayer:
    """
    Composes existing trust signals into a standard response envelope.
    Does not add new scoring models — wraps confidence, sources, and audit hooks.
    """

    CONFIDENCE_BANDS: dict[tuple[float, float], str] = {
        (0.85, 1.01): "high",
        (0.65, 0.85): "medium",
        (0.40, 0.65): "low",
        (0.0, 0.40): "insufficient",
    }

    def confidence_band(self, confidence: float) -> str:
        value = max(0.0, min(1.0, float(confidence)))
        for (lo, hi), label in self.CONFIDENCE_BANDS.items():
            if lo <= value < hi:
                return label
        return "insufficient"

    def wrap_response(
        self,
        answer: str,
        sources: list[dict[str, Any]],
        confidence: float,
        reasoning_summary: str | None,
        actions_taken: list[dict[str, Any]],
        actions_pending_approval: list[dict[str, Any]],
        advisory_only: bool,
        *,
        internal_sources: list[dict[str, Any]] | None = None,
        connector_sources: list[dict[str, Any]] | None = None,
        memory_sources: list[dict[str, Any]] | None = None,
        graph_sources: list[dict[str, Any]] | None = None,
        ml_models_used: list[str] | None = None,
        ai_systems_used: list[str] | None = None,
        assumptions: list[str] | None = None,
        risks: list[str] | None = None,
        missing_context: list[str] | None = None,
        data_freshness: str | None = None,
        recommended_next_action: str | None = None,
        routing_summary: str | None = None,
        simulation_summary: dict[str, Any] | None = None,
        action_safety_level: str | None = None,
        stale_source_warnings: list[str] | None = None,
        knowledge_freshness: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        band = self.confidence_band(confidence)
        base = {
            "answer": answer,
            "confidence": round(max(0.0, min(1.0, float(confidence))), 4),
            "confidence_band": band,
            "sources": sources,
            "reasoning_summary": reasoning_summary,
            "actions_taken": actions_taken,
            "actions_pending_approval": actions_pending_approval,
            "advisory_only": advisory_only,
            "show_why_this_answer": bool(reasoning_summary),
            "source_breakdown": {
                "internal": internal_sources or [],
                "connectors": connector_sources or [],
                "memory": memory_sources or [],
                "graph": graph_sources or [],
            },
            "ml_models_used": ml_models_used or [],
            "ai_systems_used": ai_systems_used or [],
            "assumptions": assumptions or [],
            "risks": risks or [],
            "missing_context": missing_context or [],
            "data_freshness": data_freshness,
            "recommended_next_action": recommended_next_action,
            "routing_summary": routing_summary,
            "simulation_summary": simulation_summary,
            "action_safety_level": action_safety_level or "low",
            "stale_source_warnings": stale_source_warnings or [],
            "knowledge_freshness": knowledge_freshness or {},
        }
        if stale_source_warnings:
            base["risks"] = list(risks or []) + [
                warning for warning in stale_source_warnings if warning not in (risks or [])
            ]
        return base

    def apply_freshness_to_confidence(
        self,
        confidence: float,
        *,
        stale_source_warnings: list[str] | None = None,
        freshness_penalty: float = 0.0,
    ) -> float:
        penalty = float(freshness_penalty or 0.0)
        if stale_source_warnings:
            penalty = max(penalty, min(0.2, 0.04 * len(stale_source_warnings)))
        return round(max(0.0, min(1.0, float(confidence) - penalty)), 4)

    def build_knowledge_freshness_envelope(
        self,
        retrieval_plan: dict[str, Any] | None,
    ) -> tuple[str | None, list[str], dict[str, Any]]:
        plan = retrieval_plan or {}
        warnings = list(plan.get("freshness_trust_warnings") or [])
        stale_map = plan.get("assignment_stale_warnings") or {}
        for warning in stale_map.values():
            if warning and warning not in warnings:
                warnings.append(str(warning))
        label = plan.get("freshness_label") or plan.get("data_freshness")
        envelope = {
            "freshness_label": label,
            "learning_confidence": plan.get("learning_confidence"),
            "insufficient_data": bool(plan.get("insufficient_data")),
            "stale_source_count": len(warnings),
        }
        return label, warnings, envelope

    def build_optimization_trust_metadata(
        self,
        *,
        freshness_envelope: dict[str, Any] | None = None,
        optimization_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        optimization = optimization_summary or {}
        return {
            "freshness": freshness_envelope or {},
            "domain_optimization": {
                "pending_recommendations": int(optimization.get("pending_count") or 0),
                "advisory_only": True,
                "auto_execution_enabled": False,
                "insufficient_data_warnings": optimization.get("insufficient_data_warnings") or [],
            },
        }

    async def generate_answer_explanation(
        self,
        sources: list[dict[str, Any]],
        model_used: str,
        confidence: float,
    ) -> str:
        internal = sum(1 for s in sources if s.get("type") in {"document", "rag", "internal"})
        connector = sum(1 for s in sources if s.get("type") in {"connector", "prediction"})
        band = self.confidence_band(confidence)
        return (
            f"Answer based on {internal} internal source(s) and {connector} connector/prediction source(s). "
            f"Model: {model_used}. Confidence: {confidence:.2f} ({band})."
        )

    async def generate_prediction_explanation(
        self,
        model_name: str,
        confidence: float,
        data_points_used: int,
        confidence_note: str,
    ) -> str:
        return (
            f"Prediction from {model_name} using {data_points_used} data point(s). "
            f"Confidence: {confidence:.2f}. {confidence_note}"
        )

    async def generate_missing_context_warning(
        self,
        missing_sources: list[str],
        confidence: float,
    ) -> str:
        if confidence >= 0.65:
            return ""
        missing = ", ".join(missing_sources) if missing_sources else "additional org context"
        return (
            f"Low confidence ({confidence:.2f}): answer may be incomplete because {missing} was unavailable."
        )

    def generate_action_safety_explanation(
        self,
        action_type: str,
        risk_level: str,
        approval_required: bool,
        simulation_summary: dict[str, Any] | None,
    ) -> str:
        parts = [f"Action '{action_type}' has risk level {risk_level}."]
        if approval_required:
            parts.append("Human approval is required before execution.")
        if simulation_summary:
            status = simulation_summary.get("simulation_status")
            parts.append(f"Pre-execution simulation status: {status}.")
            if simulation_summary.get("reversible") is False:
                parts.append("This action is treated as irreversible.")
        return " ".join(parts)

    def wrap_response_calibrated(
        self,
        org_id: str,
        *,
        answer: str,
        sources: list[dict[str, Any]],
        confidence: float,
        reasoning_summary: str | None,
        actions_taken: list[dict[str, Any]],
        actions_pending_approval: list[dict[str, Any]],
        advisory_only: bool,
        surface: str = "assistant",
        settings: Any | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from app.config import get_settings
        from app.services.confidence_calibrator import get_confidence_calibrator

        active = settings or get_settings()
        multiplier = get_confidence_calibrator(active).get_multiplier(org_id, surface)
        adjusted = round(max(0.0, min(1.0, float(confidence) * multiplier)), 4)
        envelope = self.wrap_response(
            answer,
            sources,
            adjusted,
            reasoning_summary,
            actions_taken,
            actions_pending_approval,
            advisory_only,
            **kwargs,
        )
        envelope["calibration_multiplier"] = multiplier
        envelope["calibrated_confidence"] = adjusted
        return envelope


_ai_trust_layer: AITrustLayer | None = None


def get_ai_trust_layer() -> AITrustLayer:
    global _ai_trust_layer
    if _ai_trust_layer is None:
        _ai_trust_layer = AITrustLayer()
    return _ai_trust_layer

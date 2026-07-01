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
    ) -> dict[str, Any]:
        band = self.confidence_band(confidence)
        return {
            "answer": answer,
            "confidence": round(max(0.0, min(1.0, float(confidence))), 4),
            "confidence_band": band,
            "sources": sources,
            "reasoning_summary": reasoning_summary,
            "actions_taken": actions_taken,
            "actions_pending_approval": actions_pending_approval,
            "advisory_only": advisory_only,
            "show_why_this_answer": bool(reasoning_summary),
        }


_ai_trust_layer: AITrustLayer | None = None


def get_ai_trust_layer() -> AITrustLayer:
    global _ai_trust_layer
    if _ai_trust_layer is None:
        _ai_trust_layer = AITrustLayer()
    return _ai_trust_layer

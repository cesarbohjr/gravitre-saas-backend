"""Executive intelligence composite scoring — centrally weighted, evolvable."""
from __future__ import annotations

from typing import Any

DEFAULT_SCORE_WEIGHTS: dict[str, float] = {
    "trust": 0.30,
    "learning": 0.25,
    "freshness": 0.20,
    "optimization": 0.15,
    "domain_health": 0.10,
}


class ExecutiveIntelligenceScoringService:
    """Computes org intelligence score from component health metrics."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.weights = dict(weights or DEFAULT_SCORE_WEIGHTS)

    def get_weights(self) -> dict[str, float]:
        return dict(self.weights)

    def compute_score(
        self,
        *,
        trust_score: float | None,
        learning_score: float | None,
        freshness_score: float | None,
        optimization_score: float | None,
        domain_health_score: float | None,
    ) -> dict[str, Any]:
        components = {
            "trust": trust_score,
            "learning": learning_score,
            "freshness": freshness_score,
            "optimization": optimization_score,
            "domain_health": domain_health_score,
        }
        available: dict[str, float] = {
            key: float(value)
            for key, value in components.items()
            if value is not None and 0.0 <= float(value) <= 1.0
        }
        if not available:
            return {
                "intelligence_score": None,
                "score_label": "insufficient_data",
                "score_breakdown": components,
                "score_weights": self.weights,
                "components_used": [],
            }

        weight_sum = sum(self.weights[key] for key in available)
        if weight_sum <= 0:
            return {
                "intelligence_score": None,
                "score_label": "insufficient_data",
                "score_breakdown": components,
                "score_weights": self.weights,
                "components_used": list(available.keys()),
            }

        weighted = sum(available[key] * self.weights[key] for key in available) / weight_sum
        score = round(max(0.0, min(1.0, weighted)), 4)
        return {
            "intelligence_score": score,
            "score_label": self._score_label(score),
            "score_breakdown": {**components, **{f"{k}_normalized": available[k] for k in available}},
            "score_weights": self.weights,
            "components_used": list(available.keys()),
        }

    @staticmethod
    def _score_label(score: float) -> str:
        if score >= 0.85:
            return "strong"
        if score >= 0.65:
            return "healthy"
        if score >= 0.45:
            return "developing"
        return "needs_attention"


_service: ExecutiveIntelligenceScoringService | None = None


def get_executive_intelligence_scoring_service() -> ExecutiveIntelligenceScoringService:
    global _service
    if _service is None:
        _service = ExecutiveIntelligenceScoringService()
    return _service

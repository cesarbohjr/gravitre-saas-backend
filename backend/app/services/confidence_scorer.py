"""Unified confidence scoring for intelligence responses."""
from __future__ import annotations


class ConfidenceScorer:
    """
    Weighted confidence from RAG quality, source reliability, ML, and classification signals.
    """

    WEIGHTS = {
        "rag_quality": 0.35,
        "source_reliability": 0.25,
        "ml_confidence": 0.25,
        "classification_confidence": 0.15,
    }

    def compute(
        self,
        rag_quality: float | None,
        source_reliability: float | None,
        ml_confidence: float | None,
        classification_confidence: float | None,
    ) -> float:
        signals = {
            "rag_quality": rag_quality,
            "source_reliability": source_reliability,
            "ml_confidence": ml_confidence,
            "classification_confidence": classification_confidence,
        }
        available = {key: value for key, value in signals.items() if value is not None}
        if not available:
            return 0.5
        total_weight = sum(self.WEIGHTS[key] for key in available)
        return sum(value * (self.WEIGHTS[key] / total_weight) for key, value in available.items())

    def compute_with_calibration(
        self,
        org_id: str,
        *,
        surface: str = "default",
        rag_quality: float | None = None,
        source_reliability: float | None = None,
        ml_confidence: float | None = None,
        classification_confidence: float | None = None,
    ) -> float:
        base = self.compute(
            rag_quality=rag_quality,
            source_reliability=source_reliability,
            ml_confidence=ml_confidence,
            classification_confidence=classification_confidence,
        )
        from app.services.confidence_calibrator import get_confidence_calibrator

        multiplier = get_confidence_calibrator().get_multiplier(org_id, surface)
        return round(min(1.0, max(0.0, base * multiplier)), 4)


_confidence_scorer: ConfidenceScorer | None = None


def get_confidence_scorer() -> ConfidenceScorer:
    global _confidence_scorer
    if _confidence_scorer is None:
        _confidence_scorer = ConfidenceScorer()
    return _confidence_scorer

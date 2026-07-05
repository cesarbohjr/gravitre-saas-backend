"""Learning confidence — how much Gravitre trusts its own adaptive learning for a segment."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings

MIN_SAMPLES_DEV = 10
MIN_SAMPLES_PROD = 20


@dataclass(frozen=True)
class LearningConfidenceAssessment:
    level: str
    sample_count: int
    positive_count: int
    negative_count: int
    noise_score: float
    min_samples_required: int
    learning_rate_multiplier: float
    insufficient_data: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "sample_count": self.sample_count,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "noise_score": round(float(self.noise_score), 4),
            "min_samples_required": self.min_samples_required,
            "learning_rate_multiplier": round(float(self.learning_rate_multiplier), 4),
            "insufficient_data": self.insufficient_data,
        }


class LearningConfidenceService:
    """Determines trust in segment learning from sample volume and signal quality."""

    RATE_BY_LEVEL: dict[str, float] = {
        "insufficient_data": 0.0,
        "low": 0.25,
        "medium": 0.6,
        "high": 1.0,
    }

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def min_samples(self) -> int:
        env = (self.settings.app_env or "dev").strip().lower()
        if env in {"prod", "production", "staging"}:
            return MIN_SAMPLES_PROD
        return MIN_SAMPLES_DEV

    def assess(
        self,
        *,
        sample_count: int,
        positive_count: int = 0,
        negative_count: int = 0,
        noise_score: float = 0.0,
    ) -> LearningConfidenceAssessment:
        samples = max(0, int(sample_count))
        positive = max(0, int(positive_count))
        negative = max(0, int(negative_count))
        noise = max(0.0, min(1.0, float(noise_score)))
        min_required = self.min_samples()

        if samples < min_required:
            return LearningConfidenceAssessment(
                level="insufficient_data",
                sample_count=samples,
                positive_count=positive,
                negative_count=negative,
                noise_score=noise,
                min_samples_required=min_required,
                learning_rate_multiplier=0.0,
                insufficient_data=True,
            )

        total_polarized = positive + negative
        positive_ratio = positive / total_polarized if total_polarized else 0.5
        level = "low"
        if samples >= min_required * 5 and positive_ratio >= 0.55 and noise <= 0.35:
            level = "high"
        elif samples >= min_required * 2 and noise <= 0.5:
            level = "medium"

        rate = self.RATE_BY_LEVEL[level] * (1.0 - (noise * 0.5))
        return LearningConfidenceAssessment(
            level=level,
            sample_count=samples,
            positive_count=positive,
            negative_count=negative,
            noise_score=noise,
            min_samples_required=min_required,
            learning_rate_multiplier=max(0.0, min(1.0, rate)),
            insufficient_data=False,
        )

    def scale_delta(self, base_delta: float, assessment: LearningConfidenceAssessment) -> float:
        if assessment.insufficient_data:
            return 0.0
        return float(base_delta) * float(assessment.learning_rate_multiplier)


_service: LearningConfidenceService | None = None


def get_learning_confidence_service(settings: Settings | None = None) -> LearningConfidenceService:
    global _service
    if _service is None or settings is not None:
        _service = LearningConfidenceService(settings)
    return _service

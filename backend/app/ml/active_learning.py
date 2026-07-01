"""Active learning coordinator — PLANNED scaffold."""
from __future__ import annotations

from typing import Any

from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel


class ActiveLearningCoordinator(CatalogScaffoldModel):
    """
    Prioritizes unlabeled examples for human review via v4 MemoryPromotionService.

    Status: PLANNED — partial equivalent in v4 confidence-gated approval queue.
    Activation: wire InferenceService confidence distributions into uncertainty sampling.
    """

    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.PLANNED
    catalog_name = "ActiveLearningCoordinator"

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        return {
            "status": "not_available",
            "model": self.catalog_name,
            "reason": "PLANNED — partial equivalent in v4 MemoryPromotionService. See docstring.",
        }

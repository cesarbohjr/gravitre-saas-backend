"""Meta-learning adaptor — PLANNED scaffold."""
from __future__ import annotations

from typing import Any

from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel


class MetaLearningAdaptor(CatalogScaffoldModel):
    """
    Few-shot adaptation for new orgs by transferring priors from similar orgs.

    Status: PLANNED — same privacy prerequisites as FederatedLearning.
    Until activated: org models start from sklearn defaults (current behavior).
    """

    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.PLANNED
    catalog_name = "MetaLearningAdaptor"

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        return {
            "status": "not_available",
            "model": self.catalog_name,
            "reason": "PLANNED — same prerequisites as FederatedLearning. See docstring.",
        }

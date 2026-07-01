"""Self-supervised embedding learner — PLANNED scaffold."""
from __future__ import annotations

from typing import Any

from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel


class SelfSupervisedEmbeddingLearner(CatalogScaffoldModel):
    """
    Learns org-specific embeddings from unlabeled document/query data.

    Status: PLANNED
    Current alternative: text-embedding-3-small (OpenAI pretrained) used throughout RAG.
    Activate only if v7 retrieval quality metrics show a measurable gap.
    """

    model_type = ModelType.EMBEDDING
    catalog_status = ModelStatus.PLANNED
    catalog_name = "SelfSupervisedEmbeddingLearner"

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        return {
            "status": "not_available",
            "model": self.catalog_name,
            "reason": "PLANNED — current embedding model is sufficient. See docstring for activation path.",
        }

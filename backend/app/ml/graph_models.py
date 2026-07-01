"""Graph neural network relationship scoring — PLANNED scaffold."""
from __future__ import annotations

from typing import Any

from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel


class GraphNeuralNetworkScorer(CatalogScaffoldModel):
    """
    GNN-based scoring over org_entity_relationships.

    Status: PLANNED
    Activation requirements:
    - 10,000+ entity relationship rows per org
    - PyTorch Geometric or DGL (not in requirements)
    - GPU training infrastructure

    Current alternative: v6 entity relationship confidence-score traversal (live).
    """

    model_type = ModelType.EMBEDDING
    catalog_status = ModelStatus.PLANNED
    catalog_name = "GraphNeuralNetworkScorer"

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        return {
            "status": "not_available",
            "model": self.catalog_name,
            "reason": "PLANNED — see activation requirements in docstring.",
            "fallback": "v6 entity relationship confidence traversal",
            "fallback_endpoint": "/api/admin/intelligence/relationships",
        }

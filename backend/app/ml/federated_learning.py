"""Federated learning coordinator — DISABLED scaffold."""
from __future__ import annotations

from typing import Any

from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel


class FederatedLearningCoordinator(CatalogScaffoldModel):
    """
    Cross-tenant privacy-preserving learning.

    Status: DISABLED
    Activation requirements (ALL required):
    1. Legal review and customer consent mechanism
    2. Flower framework or equivalent FL library
    3. Differential privacy implementation
    4. Secure gradient aggregation protocol
    5. Minimum 100 participating orgs

    Until activated: each org's models train only on that org's own data.
    """

    model_type = ModelType.EMBEDDING
    catalog_status = ModelStatus.DISABLED
    catalog_name = "FederatedLearningCoordinator"

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        return {
            "status": "disabled",
            "model": self.catalog_name,
            "reason": "DISABLED — requires legal review and dedicated FL infrastructure. See docstring.",
        }

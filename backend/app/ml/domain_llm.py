"""Domain-specific LLM routing — PLANNED scaffold."""
from __future__ import annotations

from typing import Any

from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel


class DomainSpecificLLMRouter(CatalogScaffoldModel):
    """
    Routes queries to department-fine-tuned LLMs when available.

    Status: PLANNED
    Current equivalent: model_router department overrides (admin-configurable).
    Activation: FineTunedLLM pipeline once 1000+ examples per department exist.
    """

    model_type = ModelType.FINE_TUNED_LLM
    catalog_status = ModelStatus.PLANNED
    catalog_name = "DomainSpecificLLMRouter"

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        return {
            "status": "not_available",
            "model": self.catalog_name,
            "reason": (
                "PLANNED — use model_router department overrides as equivalent. "
                "Fine-tuning activates via FineTunedLLM once data accumulates."
            ),
        }

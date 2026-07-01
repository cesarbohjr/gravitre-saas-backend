"""Diffusion / image generation connector scaffold."""
from __future__ import annotations

from typing import Any

from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel


class DiffusionModelConnector(CatalogScaffoldModel):
    """
    Connects to image/content generation providers for workflow creative steps.

    Status: PLANNED — add provider (Stability AI, DALL-E, etc.) via ToolRegistry.
    """

    model_type = ModelType.FINE_TUNED_LLM
    catalog_status = ModelStatus.PLANNED
    catalog_name = "DiffusionModelConnector"

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        return {
            "status": "not_available",
            "model": self.catalog_name,
            "reason": "PLANNED — add image generation provider via ToolRegistry.",
        }

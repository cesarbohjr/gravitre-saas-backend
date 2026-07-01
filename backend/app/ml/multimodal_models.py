"""Multimodal routing scaffold — partial coverage via model_router vision tier."""
from __future__ import annotations

from typing import Any

from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel


class MultimodalRouter(CatalogScaffoldModel):
    """
    Routes image/document/audio inputs to vision-capable models.

    Status: PLANNED (partially covered by model_router vision tier).
    Full multimodal pipeline (audio, video) requires additional provider integrations.
    """

    model_type = ModelType.FINE_TUNED_LLM
    catalog_status = ModelStatus.PLANNED
    catalog_name = "MultimodalRouter"

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        return {
            "status": "partial",
            "model": self.catalog_name,
            "available_now": "image inputs via model_router vision tier",
            "planned": "audio, video — requires provider integration",
        }

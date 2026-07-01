"""Shared scaffold for catalog models that are PLANNED or DISABLED."""
from __future__ import annotations

from typing import Any

import numpy as np

from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus


class CatalogScaffoldModel(BaseMLModel):
    """Honest scaffold — never fabricates ML outputs."""

    catalog_status: ModelStatus = ModelStatus.PLANNED
    advisory_only: bool = False
    catalog_name: str = "CatalogScaffoldModel"

    async def train(
        self,
        X: np.ndarray | list[dict],
        y: np.ndarray | list[str] | list[float] | None = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        _ = X, y, kwargs
        raise ValueError(
            f"{self.catalog_name} is {self.catalog_status.value}; training is not available yet."
        )

    async def predict(
        self,
        X: np.ndarray | list[dict],
        return_probabilities: bool = False,
        **kwargs: Any,
    ) -> tuple[list[Any], list[dict[str, float]] | None]:
        _ = X, return_probabilities
        structured = await self.predict_structured(**kwargs)
        return [structured], None

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def save(self) -> bytes:
        return b""

    def load(self, data: bytes) -> None:
        _ = data

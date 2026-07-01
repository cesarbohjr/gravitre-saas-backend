"""World model scaffold — PLANNED; honest substitute is v9 dependency impact."""
from __future__ import annotations

from typing import Any

import numpy as np

from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus, ModelType


class WorldModelScaffold(BaseMLModel):
    """
    Internal model of how business actions affect outcomes.
    Status: PLANNED — requires 6+ months v8 data + CausalImpactAnalyzer.
    """

    model_type = ModelType.REGRESSOR
    catalog_status = ModelStatus.PLANNED
    advisory_only = True
    def __init__(self) -> None:
        self._model = None

    async def train(
        self,
        X: np.ndarray | list[dict] | None = None,
        y: np.ndarray | list[float] | None = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        raise ValueError("WorldModelScaffold is PLANNED and cannot train yet.")

    async def predict(
        self,
        X: np.ndarray | list[dict],
        return_probabilities: bool = False,
        **kwargs: Any,
    ) -> tuple[list[Any], list[dict[str, float]] | None]:
        return [await self.predict_structured()], None

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "status": "not_available",
            "model": "WorldModelScaffold",
            "reason": "PLANNED — requires 6+ months outcome data and CausalImpactAnalyzer.",
            "current_substitute": "app.services.dependency_impact_service",
            "advisory_only": True,
        }

    def save(self) -> bytes:
        return b""

    def load(self, data: bytes) -> None:
        return None

"""Causal impact analysis — PLANNED scaffold."""
from __future__ import annotations

from typing import Any

from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel


class CausalImpactAnalyzer(CatalogScaffoldModel):
    """
    Estimates whether an agent action caused a metric change using ITS or DiD.

    Status: PLANNED — requires 30+ pre-action and 30+ post-action data points per metric.
    Wire to agent_action_outcomes once sufficient history accumulates.
    """

    model_type = ModelType.CAUSAL_MODEL
    catalog_status = ModelStatus.PLANNED
    advisory_only = True
    catalog_name = "CausalImpactAnalyzer"

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        return {
            "status": "not_available",
            "model": self.catalog_name,
            "reason": (
                "PLANNED — requires 30+ pre/post action data points per metric "
                "from agent_action_outcomes."
            ),
            "current_alternative": (
                "Use v8 outcome_attribution for correlational analysis with mandatory confidence_note."
            ),
            "advisory_only": True,
        }

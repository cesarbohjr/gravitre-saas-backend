"""Agentic planning model — PLANNED scaffold."""
from __future__ import annotations

from typing import Any

from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel


class AgentPlanningModel(CatalogScaffoldModel):
    """
    ML-based agent task planning from outcome trajectories.

    Status: PLANNED
    Current equivalent: ReActEngine multi-step Reason → Act → Observe planning.
    Learning extension uses v8 agent_action_outcomes once trajectory volume exists.
    """

    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.PLANNED
    advisory_only = True
    catalog_name = "AgentPlanningModel"

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        return {
            "status": "not_available",
            "model": self.catalog_name,
            "reason": (
                "PLANNED — ReActEngine is the current equivalent. "
                "See docstring for learning extension path."
            ),
            "advisory_only": True,
        }

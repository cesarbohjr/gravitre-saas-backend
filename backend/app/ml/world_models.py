"""World model scaffold — PLANNED; honest substitute is v9 dependency impact."""
from __future__ import annotations

import os
from typing import Any

import numpy as np

from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus, ModelType
from app.config import Settings, get_settings
from app.workflows.repository import get_supabase_client

SCOPE_NOTE = (
    "WorldModelScaffold remains PLANNED until all activation prerequisites are met. "
    "Substitute: dependency_impact_service + SimulationService for bounded scenarios."
)


class WorldModelScaffold(BaseMLModel):
    """
    Internal model of how business actions affect outcomes.
    Status: PLANNED — activation checklist auto-checked per org.
    """

    model_type = ModelType.REGRESSOR
    catalog_status = ModelStatus.PLANNED
    advisory_only = True
    WORLD_MODEL_MIN_TRAJECTORIES = 500

    def __init__(self) -> None:
        self._model = None

    async def _count_measured_outcomes(self, org_id: str, settings: Settings | None = None) -> int:
        active = settings or get_settings()
        client = get_supabase_client(active)
        rows = (
            client.table("agent_action_outcomes")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .execute()
        )
        return int(rows.count or 0)

    async def check_activation_status(self, org_id: str) -> dict[str, Any]:
        from app.ml.model_catalog import GRAVITRE_ML_CATALOG

        trajectory_count = await self._count_measured_outcomes(org_id)
        causal_status = GRAVITRE_ML_CATALOG.get("causal_impact_analyzer", {}).get("status", ModelStatus.PLANNED)
        if isinstance(causal_status, ModelStatus):
            causal_status = causal_status.value
        env_enabled = os.environ.get("WORLD_MODEL_ENABLED", "false").lower() == "true"
        all_met = (
            trajectory_count >= self.WORLD_MODEL_MIN_TRAJECTORIES
            and causal_status == ModelStatus.TRAINED.value
            and env_enabled
        )
        return {
            "activation_status": "active" if all_met else "planned",
            "prerequisites": {
                "outcome_trajectories": {
                    "current": trajectory_count,
                    "required": self.WORLD_MODEL_MIN_TRAJECTORIES,
                    "met": trajectory_count >= self.WORLD_MODEL_MIN_TRAJECTORIES,
                },
                "causal_inference": {
                    "status": causal_status,
                    "met": causal_status == ModelStatus.TRAINED.value,
                },
                "env_flag": {
                    "value": "WORLD_MODEL_ENABLED",
                    "met": env_enabled,
                },
            },
            "all_prerequisites_met": all_met,
            "scope_note": SCOPE_NOTE,
            "advisory_only": True,
        }

    async def _run_world_model(self, org_id: str) -> dict[str, Any]:
        return {
            "status": "active",
            "model": "WorldModelScaffold",
            "org_id": org_id,
            "note": "Activation prerequisites met — bounded world-model inference enabled.",
            "advisory_only": True,
            "scope_note": SCOPE_NOTE,
        }

    async def train(
        self,
        X: np.ndarray | list[dict] | None = None,
        y: np.ndarray | list[float] | None = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        raise ValueError("WorldModelScaffold is PLANNED and cannot train yet.")

    async def predict(
        self,
        X: np.ndarray | list[dict] | None = None,
        return_probabilities: bool = False,
        **kwargs: Any,
    ) -> tuple[list[Any], list[dict[str, float]] | None]:
        org_id = kwargs.get("org_id")
        payload = await self.predict_structured(org_id=org_id)
        return [payload], None

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        org_id = kwargs.get("org_id")
        if org_id:
            status = await self.check_activation_status(str(org_id))
            if status["all_prerequisites_met"]:
                return await self._run_world_model(str(org_id))
            return {
                "status": "not_available",
                "model": "WorldModelScaffold",
                "activation_progress": status["prerequisites"],
                "current_substitute": (
                    "v9 dependency_impact_service + SimulationService for bounded scenario estimation"
                ),
                "advisory_only": True,
                "scope_note": SCOPE_NOTE,
            }
        return {
            "status": "not_available",
            "model": "WorldModelScaffold",
            "advisory_only": True,
            "scope_note": SCOPE_NOTE,
        }

    def save(self) -> bytes:
        return b""

    def load(self, data: bytes) -> None:
        return None

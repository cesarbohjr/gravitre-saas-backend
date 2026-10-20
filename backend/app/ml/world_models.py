"""Org-local, bounded transition model; never a simulation of an entire business."""
from __future__ import annotations

import pickle
from typing import Any

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error

from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus, ModelType

SCOPE_NOTE = "Bounded observed transitions, not causal proof or permission to execute an action."


class WorldModelScaffold(BaseMLModel):
    """Retain the existing public class name for registry compatibility."""
    model_type = ModelType.REGRESSOR
    catalog_status = ModelStatus.READY
    advisory_only = True
    WORLD_MODEL_MIN_TRAJECTORIES = 500

    def __init__(self) -> None:
        self._model: Ridge | None = None
        self._features: list[str] = []
        self._low: np.ndarray | None = None
        self._high: np.ndarray | None = None

    def _matrix(self, rows: Any) -> np.ndarray:
        if not isinstance(rows, list) or not rows:
            raise ValueError("Nonempty structured transition inputs required")
        if any(not isinstance(row, dict) or set(row) != set(self._features) for row in rows):
            raise ValueError("Transition feature schema mismatch")
        result = np.asarray([[row[key] for key in self._features] for row in rows], dtype=float)
        if not np.isfinite(result).all():
            raise ValueError("Finite transition features required")
        return result

    async def train(self, X: Any, y: Any = None, **kwargs: Any) -> ModelMetrics:
        if not isinstance(X, list) or len(X) < self.WORLD_MODEL_MIN_TRAJECTORIES:
            raise ValueError("At least 500 measured transitions required")
        if not isinstance(X[0], dict) or not X[0] or len(X[0]) > 128:
            raise ValueError("1–128 transition features required")
        self._features = sorted(X[0])
        matrix = self._matrix(X)
        targets = np.asarray(y, dtype=float)
        if targets.ndim != 1 or len(targets) != len(matrix) or not np.isfinite(targets).all():
            raise ValueError("One finite measured outcome per transition required")
        split = int(len(matrix) * .8)
        model = Ridge(alpha=1.0).fit(matrix[:split], targets[:split])
        error = float(mean_absolute_error(targets[split:], model.predict(matrix[split:])))
        baseline = float(mean_absolute_error(targets[split:], np.full(len(targets) - split, targets[:split].mean())))
        # A loaded transition model must have actually outperformed the baseline.
        if error >= baseline:
            raise ValueError("Transition model did not beat held-out historical-mean baseline")
        self._model = model
        self._low, self._high = matrix[:split].min(axis=0), matrix[:split].max(axis=0)
        return ModelMetrics(mae=error, training_samples=split, validation_samples=len(matrix)-split,
                            custom_metrics={"baseline_mae": baseline, "method": "ridge_transition",
                                            "causal_proof": False})

    async def predict(self, X: Any, return_probabilities: bool = False, **kwargs: Any) -> tuple[list[Any], None]:
        if self._model is None or self._low is None or self._high is None:
            raise ValueError("No validated transition artifact loaded")
        matrix = self._matrix(X)
        if ((matrix < self._low) | (matrix > self._high)).any():
            raise ValueError("Scenario outside observed transition support")
        return self._model.predict(matrix).tolist(), None

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        if self._model is None:
            return {"status": "dormant", "model": "world_model", "reason": "validated_transition_artifact_required",
                    "advisory_only": True, "scope_note": SCOPE_NOTE}
        predictions, _ = await self.predict(kwargs.get("inputs"))
        return {"status": "ok", "model": "world_model", "predictions": predictions,
                "method": "ridge_transition", "advisory_only": True, "scope_note": SCOPE_NOTE}

    async def check_activation_status(self, org_id: str) -> dict[str, Any]:
        from app.ml.model_catalog import get_org_model_status
        status = await get_org_model_status(org_id, "world_model")
        from app.config import get_settings
        from app.ml.training_consent import training_is_approved
        loaded = status.get("artifact_loaded") is True
        permitted = await training_is_approved(org_id, "world_model", get_settings())
        return {"activation_status": "ready_for_inference" if loaded and permitted else "dormant",
                "artifact_loaded": loaded, "training_permission_approved": permitted,
                "all_prerequisites_met": loaded and permitted, "scope_note": SCOPE_NOTE,
                "advisory_only": True}

    def save(self) -> bytes:
        if self._model is None:
            raise ValueError("Cannot persist an untrained transition model")
        return pickle.dumps({"schema": 1, "model": self._model, "features": self._features,
                             "low": self._low, "high": self._high})

    def load(self, data: bytes) -> None:
        artifact = pickle.loads(data)
        if not isinstance(artifact, dict) or artifact.get("schema") != 1 or not isinstance(artifact.get("model"), Ridge):
            raise ValueError("Invalid transition artifact")
        self._model, self._features = artifact["model"], artifact["features"]
        self._low, self._high = artifact["low"], artifact["high"]

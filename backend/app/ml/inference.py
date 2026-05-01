"""Unified inference service for deployed ML models."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from app.core.logging import get_logger
from app.ml.anomaly import AnomalyDetector
from app.ml.base import ModelType, PredictionResult
from app.ml.classifiers import SklearnClassifier
from app.ml.fine_tuning import FineTunedLLM
from app.ml.forecasting import WorkflowForecaster
from app.ml.registry import get_model_registry

logger = get_logger(__name__)


class InferenceService:
    """Loads artifacts from registry and serves predictions."""

    def __init__(self):
        self._cache: dict[str, Any] = {}

    def _cache_key(self, model_id: str, version: int) -> str:
        return f"{model_id}:v{version}"

    async def _load_runtime_model(self, model_id: str, version: int, model_type: ModelType):
        key = self._cache_key(model_id, version)
        if key in self._cache:
            return self._cache[key]
        registry = get_model_registry()
        artifact = await registry.load_model_artifact(model_id=model_id, version=version)
        if model_type == ModelType.CLASSIFIER:
            runtime = SklearnClassifier()
        elif model_type == ModelType.ANOMALY_DETECTOR:
            runtime = AnomalyDetector()
        elif model_type == ModelType.FORECASTER:
            runtime = WorkflowForecaster()
        elif model_type == ModelType.FINE_TUNED_LLM:
            runtime = FineTunedLLM()
        else:
            raise ValueError(f"Unsupported model type: {model_type.value}")
        runtime.load(artifact)
        self._cache[key] = runtime
        return runtime

    async def predict(
        self,
        org_id: str,
        model_id: str,
        inputs: list[dict[str, Any]],
        version: int | None = None,
        return_probabilities: bool = False,
    ) -> PredictionResult:
        start = time.perf_counter()
        registry = get_model_registry()
        model = await registry.get_model(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")
        if model.org_id != org_id:
            raise ValueError("Model does not belong to organization")
        selected_version = version or model.deployed_version or model.current_version
        if not selected_version:
            raise ValueError("No model version available for inference")

        runtime = await self._load_runtime_model(model_id, selected_version, model.model_type)
        predictions, probabilities = await runtime.predict(inputs, return_probabilities=return_probabilities)
        latency_ms = (time.perf_counter() - start) * 1000
        result = PredictionResult(
            model_id=model_id,
            version=selected_version,
            predictions=predictions,
            probabilities=probabilities,
            latency_ms=latency_ms,
        )

        payload = json.dumps(inputs, sort_keys=True, default=str)
        input_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        await registry.log_prediction(
            org_id=org_id,
            model_id=model_id,
            version=selected_version,
            input_hash=input_hash,
            prediction={
                "predictions": predictions,
                "probabilities": probabilities,
            },
            latency_ms=latency_ms,
        )
        logger.info("model_prediction model_id=%s version=%s latency_ms=%.2f", model_id, selected_version, latency_ms)
        return result


_inference: InferenceService | None = None


def get_inference_service() -> InferenceService:
    global _inference
    if _inference is None:
        _inference = InferenceService()
    return _inference

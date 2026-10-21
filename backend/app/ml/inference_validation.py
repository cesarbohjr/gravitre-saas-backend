"""Validation of actual inference results, independent of artifact readiness."""
from __future__ import annotations

import math
from typing import Any

import numpy as np


def normalize_inference_result(value: Any) -> Any:
    """Convert NumPy runtime scalars before API/evidence serialization."""
    if isinstance(value, np.ndarray):
        return normalize_inference_result(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: normalize_inference_result(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_inference_result(item) for item in value]
    return value


def validate_inference_result(result: Any) -> None:
    """Reject nonfinite, empty or fallback predictions masquerading as success.

    This establishes execution validity only, never accuracy or outcome quality.
    """
    def finite(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                finite(item)
        elif isinstance(value, (list, tuple, np.ndarray)):
            for item in value:
                finite(item)
        elif isinstance(value, (float, np.floating)) and not math.isfinite(value):
            raise ValueError("Nonfinite model output")

    if not isinstance(result, dict) or not isinstance(result.get("status"), str):
        raise ValueError("Structured inference status required")
    finite(result)
    if result["status"] != "ok":
        return
    if "predictions" in result:
        predictions = result["predictions"]
        if not isinstance(predictions, (list, np.ndarray)) or not len(predictions):
            raise ValueError("Nonempty predictions required")
        for prediction in predictions:
            if isinstance(prediction, dict) and prediction.get("status", "ok") != "ok":
                raise ValueError("Fallback prediction is not successful inference")
        probabilities = result.get("probabilities")
        if probabilities is not None and len(probabilities) != len(predictions):
            raise ValueError("Prediction/probability cardinality mismatch")

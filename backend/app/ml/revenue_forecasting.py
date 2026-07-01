"""Revenue metric forecasting from connector-backed time series."""
from __future__ import annotations

import pickle
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.core.logging import get_logger
from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus, ModelType

logger = get_logger(__name__)

CONFIDENCE_NOTE = (
    "Forecasts are statistical projections from historical connector data — "
    "not financial guarantees. Review confidence intervals before acting."
)


class RevenueForecaster(BaseMLModel):
    """
    Forecasts revenue metrics (deal_amount, subscription_mrr, invoice_balance)
    from historical connector data.

    Uses statsmodels ExponentialSmoothing when available; simple moving-average
    fallback otherwise. Requires MIN_HISTORY_POINTS data points.
    """

    model_type = ModelType.REGRESSOR
    catalog_status = ModelStatus.TRAINED
    advisory_only = True
    MIN_HISTORY_POINTS = 14

    def __init__(self) -> None:
        self._series: list[float] = []
        self._metric_name = "deal_amount"
        self._fitted = False
        self._model: Any = None

    async def train(
        self,
        X: np.ndarray | list[dict],
        y: np.ndarray | list[float] | None = None,
        *,
        time_series: list[dict] | None = None,
        metric_name: str = "deal_amount",
        **kwargs: Any,
    ) -> ModelMetrics:
        _ = X, kwargs
        rows = time_series or (list(X) if isinstance(X, list) else [])
        values = [float(r.get("value", r.get("metric_value", 0))) for r in rows if r]
        if y is not None and not values:
            values = [float(v) for v in y]
        if len(values) < self.MIN_HISTORY_POINTS:
            raise ValueError(
                f"Need at least {self.MIN_HISTORY_POINTS} history points, got {len(values)}"
            )
        self._series = values
        self._metric_name = metric_name
        self._fitted = True
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            self._model = ExponentialSmoothing(
                np.array(values),
                trend="add",
                seasonal=None,
                initialization_method="estimated",
            ).fit(optimized=True)
        except Exception as exc:  # noqa: BLE001
            logger.debug("revenue_forecaster_statsmodels_unavailable error=%s", exc)
            self._model = None
        holdout = max(3, len(values) // 5)
        train_vals = values[:-holdout]
        test_vals = values[-holdout:]
        baseline = sum(train_vals) / len(train_vals)
        mae = mean_absolute_error(test_vals, [baseline] * len(test_vals))
        return ModelMetrics(
            mae=mae,
            mse=mean_squared_error(test_vals, [baseline] * len(test_vals)),
            training_samples=len(train_vals),
            validation_samples=len(test_vals),
            custom_metrics={"metric_name": metric_name, "algorithm": "exponential_smoothing_or_baseline"},
        )

    async def predict(
        self,
        X: np.ndarray | list[dict],
        return_probabilities: bool = False,
        *,
        horizon_days: int = 30,
        **kwargs: Any,
    ) -> tuple[list[Any], list[dict[str, float]] | None]:
        _ = X, return_probabilities, kwargs
        structured = await self.predict_structured(horizon_days=horizon_days)
        return [structured], None

    async def predict_structured(self, *, horizon_days: int = 30) -> dict[str, Any]:
        if not self._fitted or len(self._series) < self.MIN_HISTORY_POINTS:
            return {
                "status": "insufficient_data",
                "metric_name": self._metric_name,
                "forecast_horizon_days": horizon_days,
                "data_points_used": len(self._series),
                "confidence_note": CONFIDENCE_NOTE,
                "reason": f"Need at least {self.MIN_HISTORY_POINTS} historical points.",
                "advisory_only": True,
            }
        steps = max(1, horizon_days // 7)
        if self._model is not None:
            forecast = self._model.forecast(steps)
            predicted = [float(v) for v in forecast]
        else:
            avg = sum(self._series[-self.MIN_HISTORY_POINTS :]) / self.MIN_HISTORY_POINTS
            predicted = [avg] * steps
        std = float(np.std(self._series[-self.MIN_HISTORY_POINTS :])) or abs(predicted[0]) * 0.1
        lower = [max(0.0, p - 1.96 * std) for p in predicted]
        upper = [p + 1.96 * std for p in predicted]
        return {
            "status": "ok",
            "metric_name": self._metric_name,
            "forecast_horizon_days": horizon_days,
            "predicted_values": predicted,
            "confidence_interval_lower": lower,
            "confidence_interval_upper": upper,
            "data_points_used": len(self._series),
            "confidence_note": CONFIDENCE_NOTE,
            "advisory_only": True,
        }

    def save(self) -> bytes:
        return pickle.dumps(
            {
                "series": self._series,
                "metric_name": self._metric_name,
                "fitted": self._fitted,
                "model": self._model,
            }
        )

    def load(self, data: bytes) -> None:
        loaded = pickle.loads(data)
        self._series = loaded["series"]
        self._metric_name = loaded["metric_name"]
        self._fitted = loaded["fitted"]
        self._model = loaded.get("model")

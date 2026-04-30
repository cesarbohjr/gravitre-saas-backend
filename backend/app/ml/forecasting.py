"""Time series forecasting for workflow outcomes."""
from __future__ import annotations

import pickle
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from app.core.logging import get_logger
from app.ml.base import BaseMLModel, ModelMetrics, ModelType

logger = get_logger(__name__)


class WorkflowForecaster(BaseMLModel):
    """Forecast workflow execution times and outcomes."""

    model_type = ModelType.FORECASTER

    def __init__(
        self,
        target: str = "duration_ms",
        algorithm: str = "gradient_boosting",
        forecast_horizon: int = 7,
        **kwargs: Any,
    ):
        self.target = target
        self.algorithm = algorithm
        self.forecast_horizon = forecast_horizon
        self.kwargs = kwargs
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names: list[str] = []

    def _create_model(self):
        if self.algorithm == "gradient_boosting":
            return GradientBoostingRegressor(
                n_estimators=self.kwargs.get("n_estimators", 100),
                max_depth=self.kwargs.get("max_depth", 5),
                learning_rate=self.kwargs.get("learning_rate", 0.1),
                random_state=42,
            )
        if self.algorithm == "random_forest":
            return RandomForestRegressor(
                n_estimators=self.kwargs.get("n_estimators", 100),
                max_depth=self.kwargs.get("max_depth", 10),
                random_state=42,
                n_jobs=-1,
            )
        if self.algorithm == "ridge":
            return Ridge(alpha=self.kwargs.get("alpha", 1.0))
        raise ValueError(f"Unknown algorithm: {self.algorithm}")

    def _extract_time_features(self, timestamps: list[datetime]) -> np.ndarray:
        features = []
        for ts in timestamps:
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            features.append([ts.hour, ts.weekday(), ts.day, ts.month, 1 if ts.weekday() >= 5 else 0, 1 if 9 <= ts.hour <= 17 else 0])
        return np.array(features)

    async def train(
        self,
        X: np.ndarray | list[dict],
        y: np.ndarray | list[float],
        feature_names: list[str] | None = None,
        timestamps: list[datetime] | None = None,
        validation_split: float = 0.2,
        **kwargs: Any,
    ) -> ModelMetrics:
        _ = kwargs
        import time
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        from sklearn.model_selection import train_test_split

        start_time = time.time()
        if isinstance(X, list) and X and isinstance(X[0], dict):
            feature_names = feature_names or list(X[0].keys())
            X = np.array([[row.get(f, 0) for f in feature_names] for row in X])
        if timestamps:
            time_features = self._extract_time_features(timestamps)
            X = np.hstack([X, time_features])
            feature_names = (feature_names or []) + ["hour", "weekday", "day", "month", "is_weekend", "is_business_hours"]

        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        y = np.array(y)
        X_scaled = self.scaler.fit_transform(X)
        X_train, X_val, y_train, y_val = train_test_split(X_scaled, y, test_size=validation_split, random_state=42)
        self.model = self._create_model()
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_val)
        metrics = ModelMetrics(
            mse=mean_squared_error(y_val, y_pred),
            mae=mean_absolute_error(y_val, y_pred),
            r2_score=r2_score(y_val, y_pred),
            training_samples=len(X_train),
            validation_samples=len(X_val),
            training_duration_seconds=time.time() - start_time,
            custom_metrics={
                "rmse": float(np.sqrt(mean_squared_error(y_val, y_pred))),
                "target": self.target,
                "algorithm": self.algorithm,
            },
        )
        logger.info(
            "forecaster_trained target=%s algo=%s r2=%.4f mae=%.4f",
            self.target,
            self.algorithm,
            metrics.r2_score or 0.0,
            metrics.mae or 0.0,
        )
        return metrics

    async def predict(
        self,
        X: np.ndarray | list[dict],
        return_probabilities: bool = False,
        timestamps: list[datetime] | None = None,
        **kwargs: Any,
    ) -> tuple[list[float], list[dict[str, float]] | None]:
        _ = kwargs
        if self.model is None:
            raise ValueError("Model not trained")
        if isinstance(X, list) and X and isinstance(X[0], dict):
            base_features = [name for name in self.feature_names if name not in {"hour", "weekday", "day", "month", "is_weekend", "is_business_hours"}]
            X = np.array([[row.get(f, 0) for f in base_features] for row in X])
        if timestamps:
            time_features = self._extract_time_features(timestamps)
            X = np.hstack([X, time_features])
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled).tolist()
        intervals = None
        if return_probabilities:
            intervals = [{"prediction": float(p), "lower_bound": float(p * 0.8), "upper_bound": float(p * 1.2)} for p in predictions]
        return [float(p) for p in predictions], intervals

    async def forecast_workflow_duration(
        self,
        workflow_id: str,
        historical_runs: list[dict],
        forecast_timestamps: list[datetime] | None = None,
    ) -> list[dict]:
        _ = workflow_id
        if not historical_runs:
            return []
        latest = historical_runs[-1]
        base_features = {
            "step_count": latest.get("step_count", 5),
            "connector_count": latest.get("connector_count", 2),
            "decision_count": latest.get("decision_count", 1),
        }
        if not forecast_timestamps:
            now = datetime.now()
            forecast_timestamps = [now + timedelta(days=i) for i in range(self.forecast_horizon)]
        X = [base_features for _ in forecast_timestamps]
        predictions, intervals = await self.predict(X, return_probabilities=True, timestamps=forecast_timestamps)
        intervals = intervals or []
        return [
            {"timestamp": ts.isoformat(), "predicted_duration_ms": pred, "confidence_interval": interval}
            for ts, pred, interval in zip(forecast_timestamps, predictions, intervals)
        ]

    def save(self) -> bytes:
        return pickle.dumps(
            {
                "target": self.target,
                "algorithm": self.algorithm,
                "forecast_horizon": self.forecast_horizon,
                "kwargs": self.kwargs,
                "model": self.model,
                "scaler": self.scaler,
                "feature_names": self.feature_names,
            }
        )

    def load(self, data: bytes) -> None:
        loaded = pickle.loads(data)
        self.target = loaded["target"]
        self.algorithm = loaded["algorithm"]
        self.forecast_horizon = loaded["forecast_horizon"]
        self.kwargs = loaded["kwargs"]
        self.model = loaded["model"]
        self.scaler = loaded["scaler"]
        self.feature_names = loaded["feature_names"]

    def get_feature_importance(self) -> dict[str, float] | None:
        if self.model is None:
            return None
        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
        elif hasattr(self.model, "coef_"):
            importances = np.abs(self.model.coef_)
        else:
            return None
        return {
            name: float(imp)
            for name, imp in sorted(zip(self.feature_names, importances), key=lambda x: x[1], reverse=True)
        }


class WorkflowSuccessPredictor(WorkflowForecaster):
    """Predict probability of workflow success."""

    def __init__(self, **kwargs: Any):
        super().__init__(target="success_probability", **kwargs)
        self._classifier = None

    async def train(self, X: np.ndarray | list[dict], y: np.ndarray | list[bool], **kwargs: Any) -> ModelMetrics:
        _ = kwargs
        import time
        from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
        from sklearn.model_selection import train_test_split

        start_time = time.time()
        if isinstance(X, list) and X and isinstance(X[0], dict):
            feature_names = list(X[0].keys())
            X = np.array([[row.get(f, 0) for f in feature_names] for row in X])
            self.feature_names = feature_names

        y = np.array(y).astype(int)
        X_scaled = self.scaler.fit_transform(X)
        X_train, X_val, y_train, y_val = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42, stratify=y
        )
        self._classifier = GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42)
        self._classifier.fit(X_train, y_train)
        y_pred = self._classifier.predict(X_val)
        y_proba = self._classifier.predict_proba(X_val)[:, 1]
        return ModelMetrics(
            accuracy=accuracy_score(y_val, y_pred),
            precision=precision_score(y_val, y_pred),
            recall=recall_score(y_val, y_pred),
            auc_roc=roc_auc_score(y_val, y_proba),
            training_samples=len(X_train),
            validation_samples=len(X_val),
            training_duration_seconds=time.time() - start_time,
        )

    async def predict_success(self, X: np.ndarray | list[dict]) -> list[dict]:
        if self._classifier is None:
            raise ValueError("Model not trained")
        if isinstance(X, list) and X and isinstance(X[0], dict):
            X = np.array([[row.get(f, 0) for f in self.feature_names] for row in X])
        X_scaled = self.scaler.transform(X)
        probabilities = self._classifier.predict_proba(X_scaled)
        return [
            {
                "success_probability": float(p[1]),
                "failure_probability": float(p[0]),
                "prediction": "success" if p[1] > 0.5 else "failure",
                "confidence": float(max(p)),
            }
            for p in probabilities
        ]

"""Anomaly detection for workflow patterns."""
from __future__ import annotations

import pickle
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

from app.core.logging import get_logger
from app.ml.base import BaseMLModel, ModelMetrics, ModelType

logger = get_logger(__name__)


class AnomalyDetector(BaseMLModel):
    """Anomaly detection using Isolation Forest and LOF."""

    model_type = ModelType.ANOMALY_DETECTOR

    def __init__(
        self,
        algorithm: str = "isolation_forest",
        contamination: float = 0.1,
        **kwargs: Any,
    ):
        self.algorithm = algorithm
        self.contamination = contamination
        self.kwargs = kwargs
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names: list[str] = []
        self._threshold: float | None = None

    def _create_model(self):
        if self.algorithm == "isolation_forest":
            return IsolationForest(
                contamination=self.contamination,
                n_estimators=self.kwargs.get("n_estimators", 100),
                max_samples="auto",
                random_state=42,
                n_jobs=-1,
            )
        if self.algorithm == "lof":
            return LocalOutlierFactor(
                contamination=self.contamination,
                n_neighbors=self.kwargs.get("n_neighbors", 20),
                novelty=True,
                n_jobs=-1,
            )
        raise ValueError(f"Unknown algorithm: {self.algorithm}")

    async def train(
        self,
        X: np.ndarray | list[dict],
        y: np.ndarray | None = None,
        feature_names: list[str] | None = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        _ = y, kwargs
        import time

        start_time = time.time()
        if isinstance(X, list) and X and isinstance(X[0], dict):
            feature_names = feature_names or list(X[0].keys())
            X = np.array([[row.get(f, 0) for f in feature_names] for row in X])

        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        X_scaled = self.scaler.fit_transform(X)
        self.model = self._create_model()
        self.model.fit(X_scaled)
        scores = self.model.decision_function(X_scaled)
        self._threshold = np.percentile(scores, self.contamination * 100)
        predictions = self.model.predict(X_scaled)
        n_anomalies = (predictions == -1).sum()

        metrics = ModelMetrics(
            training_samples=len(X),
            training_duration_seconds=time.time() - start_time,
            custom_metrics={
                "algorithm": self.algorithm,
                "contamination": self.contamination,
                "threshold": float(self._threshold),
                "anomalies_detected": int(n_anomalies),
                "anomaly_rate": float(n_anomalies / len(X)),
                "mean_score": float(scores.mean()),
                "std_score": float(scores.std()),
            },
        )
        logger.info(
            "anomaly_detector_trained algorithm=%s samples=%s anomalies=%s",
            self.algorithm,
            len(X),
            int(n_anomalies),
        )
        return metrics

    async def predict(
        self,
        X: np.ndarray | list[dict],
        return_probabilities: bool = False,
        **kwargs: Any,
    ) -> tuple[list[bool], list[dict[str, float]] | None]:
        _ = kwargs
        if self.model is None:
            raise ValueError("Model not trained")
        if isinstance(X, list) and X and isinstance(X[0], dict):
            X = np.array([[row.get(f, 0) for f in self.feature_names] for row in X])
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        is_anomaly = [p == -1 for p in predictions]
        scores = None
        if return_probabilities:
            raw_scores = self.model.decision_function(X_scaled)
            normalized = 1 - (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min() + 1e-10)
            scores = [{"anomaly_score": float(s), "raw_score": float(r)} for s, r in zip(normalized, raw_scores)]
        return is_anomaly, scores

    async def detect_workflow_anomalies(self, workflow_metrics: list[dict]) -> list[dict]:
        is_anomaly, scores = await self.predict(workflow_metrics, return_probabilities=True)
        scores = scores or []
        results = []
        for i, (anomaly, score, metrics) in enumerate(zip(is_anomaly, scores, workflow_metrics)):
            results.append(
                {
                    "index": i,
                    "is_anomaly": anomaly,
                    "anomaly_score": score["anomaly_score"],
                    "raw_score": score["raw_score"],
                    "metrics": metrics,
                    "reason": self._explain_anomaly(metrics, anomaly) if anomaly else None,
                }
            )
        return results

    def _explain_anomaly(self, metrics: dict, is_anomaly: bool) -> str | None:
        if not is_anomaly:
            return None
        explanations = []
        if metrics.get("duration_ms", 0) > 60000:
            explanations.append("unusually long duration")
        if metrics.get("error_count", 0) > 0:
            explanations.append(f"{metrics['error_count']} errors occurred")
        if metrics.get("retry_count", 0) > 2:
            explanations.append(f"high retry count ({metrics['retry_count']})")
        return "; ".join(explanations) if explanations else "unusual pattern detected"

    def save(self) -> bytes:
        return pickle.dumps(
            {
                "algorithm": self.algorithm,
                "contamination": self.contamination,
                "kwargs": self.kwargs,
                "model": self.model,
                "scaler": self.scaler,
                "feature_names": self.feature_names,
                "_threshold": self._threshold,
            }
        )

    def load(self, data: bytes) -> None:
        loaded = pickle.loads(data)
        self.algorithm = loaded["algorithm"]
        self.contamination = loaded["contamination"]
        self.kwargs = loaded["kwargs"]
        self.model = loaded["model"]
        self.scaler = loaded["scaler"]
        self.feature_names = loaded["feature_names"]
        self._threshold = loaded["_threshold"]


_anomaly_detector: AnomalyDetector | None = None


def get_anomaly_detector(**kwargs: Any) -> AnomalyDetector:
    """Get or create anomaly detector."""
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector(**kwargs)
    return _anomaly_detector

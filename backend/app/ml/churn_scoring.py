"""Customer churn / risk scoring from connector engagement signals."""
from __future__ import annotations

import pickle
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus, ModelType

FEATURE_KEYS = (
    "days_since_last_activity",
    "open_support_tickets",
    "failed_payments_30d",
    "deal_stage_regressions",
    "email_engagement_score",
)


class ChurnRiskScorer(BaseMLModel):
    """
    Binary classifier predicting customer churn risk from CRM/support signals.

    advisory_only=True — surfaces through v10/Meson, never auto-contacts customers.
    """

    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.TRAINED
    advisory_only = True
    MIN_TRAINING_EXAMPLES = 30

    def __init__(self) -> None:
        self._model: GradientBoostingClassifier | LogisticRegression | None = None
        self._feature_names = list(FEATURE_KEYS)

    def _vectorize(self, rows: list[dict]) -> np.ndarray:
        return np.array([[float(row.get(k) or 0.0) for k in self._feature_names] for row in rows])

    async def train(
        self,
        X: np.ndarray | list[dict],
        y: np.ndarray | list[str] | list[float] | None = None,
        *,
        features: list[dict] | None = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        _ = kwargs
        rows = features or (list(X) if isinstance(X, list) else [])
        if len(rows) < self.MIN_TRAINING_EXAMPLES:
            raise ValueError(
                f"Need at least {self.MIN_TRAINING_EXAMPLES} examples, got {len(rows)}"
            )
        if y is None:
            raise ValueError("Labels required for ChurnRiskScorer.train")
        labels = np.array([1 if bool(v) else 0 for v in y])
        matrix = self._vectorize(rows)
        x_train, x_test, y_train, y_test = train_test_split(
            matrix, labels, test_size=0.2, random_state=42, stratify=labels
        )
        try:
            model: GradientBoostingClassifier | LogisticRegression = GradientBoostingClassifier(
                random_state=42
            )
            model.fit(x_train, y_train)
        except Exception:  # noqa: BLE001
            model = LogisticRegression(max_iter=1000)
            model.fit(x_train, y_train)
        self._model = model
        y_pred = model.predict(x_test)
        y_proba = model.predict_proba(x_test)[:, 1]
        return ModelMetrics(
            accuracy=accuracy_score(y_test, y_pred),
            auc_roc=roc_auc_score(y_test, y_proba) if len(set(y_test)) > 1 else None,
            training_samples=len(x_train),
            validation_samples=len(x_test),
        )

    async def predict(
        self,
        X: np.ndarray | list[dict],
        return_probabilities: bool = False,
        *,
        customer_features: dict | None = None,
        **kwargs: Any,
    ) -> tuple[list[Any], list[dict[str, float]] | None]:
        _ = return_probabilities, kwargs
        features = customer_features or (X[0] if isinstance(X, list) and X else {})
        structured = await self.predict_structured(customer_features=features)
        return [structured], None

    async def predict_structured(self, *, customer_features: dict | None = None) -> dict[str, Any]:
        if self._model is None:
            return {
                "status": "not_trained",
                "risk_level": "unknown",
                "risk_score": 0.0,
                "contributing_factors": [],
                "recommended_action": "Train churn model once 30+ labeled customer examples exist.",
                "confidence": 0.0,
                "advisory_only": True,
                "reason": f"Need at least {self.MIN_TRAINING_EXAMPLES} training examples.",
            }
        row = customer_features or {}
        vector = self._vectorize([row])
        proba = float(self._model.predict_proba(vector)[0][1])
        if proba >= 0.7:
            level = "high"
        elif proba >= 0.4:
            level = "medium"
        else:
            level = "low"
        factors = [
            key.replace("_", " ")
            for key in self._feature_names
            if float(row.get(key) or 0.0) > 0
        ]
        return {
            "status": "ok",
            "risk_level": level,
            "risk_score": round(proba, 4),
            "contributing_factors": factors or ["insufficient feature signal"],
            "recommended_action": (
                "Review account health and route a human-gated optimization suggestion."
                if level != "low"
                else "Monitor — no immediate action suggested."
            ),
            "confidence": round(min(1.0, proba if level == "high" else 1.0 - proba), 4),
            "advisory_only": True,
        }

    def save(self) -> bytes:
        return pickle.dumps({"model": self._model, "feature_names": self._feature_names})

    def load(self, data: bytes) -> None:
        loaded = pickle.loads(data)
        self._model = loaded["model"]
        self._feature_names = loaded.get("feature_names", list(FEATURE_KEYS))

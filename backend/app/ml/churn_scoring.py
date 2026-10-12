"""Customer churn / risk scoring from connector engagement signals."""
from __future__ import annotations

import pickle
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline, make_pipeline

from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus, ModelType
from app.ml.splits import time_split

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

    def __init__(self, feature_names: list[str] | tuple[str, ...] | None = None) -> None:
        self._model: GradientBoostingClassifier | LogisticRegression | Pipeline | None = None
        self._feature_names = list(feature_names or FEATURE_KEYS)

    @property
    def feature_names(self) -> list[str]:
        return list(self._feature_names)

    def has_optional_features(self) -> bool:
        """True when the model uses features beyond the five CRM keys (entity features)."""
        return any(k not in FEATURE_KEYS for k in self._feature_names)

    @staticmethod
    def _value(row: dict, key: str) -> float:
        raw = row.get(key)
        if key in FEATURE_KEYS:
            # The CRM contract has always read a missing key as 0; unchanged.
            return float(raw or 0.0)
        # Optional (entity) features: missing means "no evidence", never 0.
        if raw is None:
            return float("nan")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return float("nan")

    def _vectorize(self, rows: list[dict]) -> np.ndarray:
        return np.array([[self._value(row, k) for k in self._feature_names] for row in rows], dtype=float)

    def _fit(self, x_train: np.ndarray, y_train: np.ndarray) -> None:
        """Fit on a prepared matrix. Optional features go through a median imputer
        with missing-indicator columns, so "no evidence" stays distinguishable."""
        optional = self.has_optional_features()

        def _wrap(estimator: Any) -> Any:
            if not optional:
                return estimator
            return make_pipeline(
                SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
                estimator,
            )

        try:
            model = _wrap(GradientBoostingClassifier(random_state=42))
            model.fit(x_train, y_train)
        except Exception:  # noqa: BLE001
            model = _wrap(LogisticRegression(max_iter=1000))
            model.fit(x_train, y_train)
        self._model = model

    async def train(
        self,
        X: np.ndarray | list[dict],
        y: np.ndarray | list[str] | list[float] | None = None,
        *,
        features: list[dict] | None = None,
        observed_at: list[Any] | None = None,
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
        split = time_split(list(observed_at or []), labels.tolist()) if observed_at else None
        if split is not None:
            # Train on earlier outcomes, hold out the latest (Phase 6).
            train_idx, hold_idx, holdout_from = split
            x_train, x_test = matrix[train_idx], matrix[hold_idx]
            y_train, y_test = labels[train_idx], labels[hold_idx]
            split_info: dict[str, Any] = {"split": "time", "holdout_from": holdout_from}
        else:
            x_train, x_test, y_train, y_test = train_test_split(
                matrix, labels, test_size=0.2, random_state=42, stratify=labels
            )
            split_info = {"split": "random"}
        self._fit(x_train, y_train)
        model = self._model
        y_pred = model.predict(x_test)
        y_proba = model.predict_proba(x_test)[:, 1]
        return ModelMetrics(
            accuracy=accuracy_score(y_test, y_pred),
            auc_roc=roc_auc_score(y_test, y_proba) if len(set(y_test)) > 1 else None,
            training_samples=len(x_train),
            validation_samples=len(x_test),
            custom_metrics=split_info,
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
            if key in FEATURE_KEYS and float(row.get(key) or 0.0) > 0
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

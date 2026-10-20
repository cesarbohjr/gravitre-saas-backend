"""Predictive ops models — org-scoped training from agent_action_outcomes."""
from __future__ import annotations

import pickle
import asyncio
from typing import Any

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import TimeSeriesSplit
from sklearn.utils.validation import check_is_fitted
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, mean_absolute_error, roc_auc_score, log_loss, brier_score_loss

from app.config import Settings, get_settings
from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus, ModelType
from app.workflows.repository import get_supabase_client

MIN_SLA_TICKET_SAMPLES = 60
MIN_DEAL_LOSS_LABELS = 25
MIN_CAPACITY_SERIES = 21

SLA_FEATURE_KEYS = (
    "open_tickets",
    "avg_resolution_hours",
    "backlog_ratio",
    "weekend_load",
    "escalation_rate",
)

DEAL_FEATURE_KEYS = (
    "deal_stage_index",
    "days_in_stage",
    "deal_amount",
    "engagement_score",
    "activity_count",
)


def _vectorize(rows: list[dict], keys: tuple[str, ...] | list[str]) -> np.ndarray:
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) or any(key not in row for key in keys) for row in rows):
        raise ValueError("Complete real feature rows required; missing features are not zero")
    values = [[row[key] for key in keys] for row in rows]
    if any(isinstance(value, (bool, str)) or not isinstance(value, (int, float, np.number)) for row in values for value in row):
        raise ValueError("Numeric risk features required")
    matrix = np.asarray(values, dtype=float)
    if not np.isfinite(matrix).all():
        raise ValueError("Finite risk features required")
    return matrix


def _fit_binary_risk(rows: list[dict], y: Any, keys: list[str], minimum: int, training_split: int | None = None, calibration_splits: Any = None) -> tuple[Any, ModelMetrics]:
    matrix = _vectorize(rows, keys)
    if len(rows) < minimum:
        raise ValueError(f"Need at least {minimum} examples, got {len(rows)}")
    if y is None or len(y) != len(rows) or any(not isinstance(v, (int, float, bool, np.number, np.bool_)) or v not in (0, 1) for v in y):
        raise ValueError("Explicit aligned binary labels required; strings are not Boolean labels")
    labels = np.asarray(y, dtype=int)
    split = int(len(rows)*.8) if training_split is None else training_split
    if type(split) is not int or not 1 <= split < len(rows):
        raise ValueError("Valid temporal holdout boundary required")
    x_train, x_test, y_train, y_test = matrix[:split], matrix[split:], labels[:split], labels[split:]
    if len(set(y_train)) != 2 or len(set(y_test)) != 2:
        raise ValueError("Both classes required in training and temporal holdout")
    folds = list(TimeSeriesSplit(n_splits=3).split(x_train)) if calibration_splits is None else calibration_splits
    if not isinstance(folds, list) or len(folds) != 3:
        raise ValueError("Three temporal calibration folds required")
    for training, calibration in folds:
        for indices in (training, calibration):
            values = np.asarray(indices)
            if values.ndim != 1 or not len(values) or not np.issubdtype(values.dtype, np.integer) or values.min() < 0 or values.max() >= len(x_train):
                raise ValueError("Valid temporal calibration indices required")
        if max(training) >= min(calibration):
            raise ValueError("Calibration must follow training without overlapping samples")
    if any(len(set(y_train[a])) != 2 or len(set(y_train[b])) != 2 for a, b in folds):
        raise ValueError("Both classes required in each temporal calibration fold")
    model = CalibratedClassifierCV(estimator=GradientBoostingClassifier(random_state=42),
                                   method="sigmoid", cv=folds, ensemble=True, n_jobs=1)
    model.fit(x_train, y_train)
    probability = model.predict_proba(x_test)[:, 1]
    auc = float(roc_auc_score(y_test, probability))
    loss = float(log_loss(y_test, probability))
    baseline_loss = float(log_loss(y_test, np.full(len(y_test), y_train.mean())))
    if auc <= .5 or loss >= baseline_loss:
        raise ValueError("Risk model must beat prior baseline on untouched temporal holdout")
    return model, ModelMetrics(accuracy=float(accuracy_score(y_test, probability >= .5)), auc_roc=auc,
                               training_samples=len(x_train), validation_samples=len(x_test),
                               custom_metrics={"split": "temporal", "calibration": "sigmoid_time_series_ensemble",
                                               "holdout_log_loss": loss, "prior_log_loss": baseline_loss,
                                               "holdout_brier_score": float(brier_score_loss(y_test, probability))})


def _load_risk_artifact(data: bytes, expected: tuple[str, ...]) -> tuple[Any, list[str]]:
    artifact = pickle.loads(data)
    if not isinstance(artifact, dict) or artifact.get("feature_names") != list(expected):
        raise ValueError("Risk artifact feature schema mismatch")
    model = artifact.get("model")
    if not isinstance(model, (GradientBoostingClassifier, LogisticRegression, CalibratedClassifierCV)):
        raise ValueError("Fitted risk classifier required")
    check_is_fitted(model)
    if model.n_features_in_ != len(expected) or list(model.classes_) != [0, 1]:
        raise ValueError("Risk classifier feature/class schema mismatch")
    return model, list(expected)


class SlaBreachPredictor(BaseMLModel):
    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.TRAINED
    advisory_only = True
    MIN_TRAINING_EXAMPLES = MIN_SLA_TICKET_SAMPLES

    def __init__(self) -> None:
        self._model: GradientBoostingClassifier | LogisticRegression | CalibratedClassifierCV | None = None
        self._feature_names = list(SLA_FEATURE_KEYS)

    async def train(self, X: Any, y: Any = None, *, features: list[dict] | None = None, **kwargs: Any) -> ModelMetrics:
        rows = features if features is not None else X
        model, metrics = await asyncio.to_thread(_fit_binary_risk, rows, y, self._feature_names, self.MIN_TRAINING_EXAMPLES,
                                                   kwargs.get("training_split"), kwargs.get("calibration_splits"))
        self._model = model
        return metrics

    async def predict(self, X: Any, return_probabilities: bool = False, **kwargs: Any) -> tuple[list[Any], Any]:
        if not isinstance(X, list) or not 1 <= len(X) <= 100:
            raise ValueError("1-100 real entity feature rows required")
        _vectorize(X, self._feature_names)
        results = [await self.predict_structured(ticket_features=row, **{key: value for key, value in kwargs.items()
                          if key not in {"features", "ticket_features", "deal_features"}}) for row in X]
        return results, None

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        org_id = str(kwargs.get("org_id") or "")
        settings = kwargs.get("settings") or get_settings()
        features = kwargs.get("ticket_features") or kwargs.get("features") or {}
        if self._model is None:
            count = await self._count_ticket_signals(org_id, settings) if org_id else 0
            return {
                "status": "not_trained",
                "model": "sla_breach_predictor",
                "risk_score": 0.0,
                "data_gate": {
                    "current": count,
                    "required": MIN_SLA_TICKET_SAMPLES,
                    "met": count >= MIN_SLA_TICKET_SAMPLES,
                },
                "reason": f"Train after {MIN_SLA_TICKET_SAMPLES}+ SLA history rows exist.",
                "advisory_only": True,
            }
        vector = _vectorize([features], self._feature_names)
        proba = float(self._model.predict_proba(vector)[0][1])
        level = "high" if proba >= 0.65 else "medium" if proba >= 0.4 else "low"
        return {
            "status": "ok",
            "model": "sla_breach_predictor",
            "risk_level": level,
            "risk_score": round(proba, 4),
            "confidence": round(max(proba, 1.0 - proba), 4),
            "drivers": [k.replace("_", " ") for k in self._feature_names if float(features.get(k) or 0) > 0],
            "advisory_only": True,
        }

    async def _count_ticket_signals(self, org_id: str, settings: Settings) -> int:
        from app.ml.bound_training_data import collect_bound_records
        try:
            rows = await asyncio.to_thread(collect_bound_records, org_id, "sla_breach_predictor", settings, include_inputs=False)
            return len(rows)
        except Exception:
            return 0

    def save(self) -> bytes:
        if self._model is None:
            raise ValueError("Untrained risk model cannot be serialized as a valid artifact")
        return pickle.dumps({"model": self._model, "feature_names": self._feature_names})

    def load(self, data: bytes) -> None:
        self._model, self._feature_names = _load_risk_artifact(data, SLA_FEATURE_KEYS)


class DealLossScorer(BaseMLModel):
    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.TRAINED
    advisory_only = True
    MIN_TRAINING_EXAMPLES = MIN_DEAL_LOSS_LABELS

    def __init__(self) -> None:
        self._model: GradientBoostingClassifier | LogisticRegression | CalibratedClassifierCV | None = None
        self._feature_names = list(DEAL_FEATURE_KEYS)

    async def train(self, X: Any, y: Any = None, *, features: list[dict] | None = None, **kwargs: Any) -> ModelMetrics:
        rows = features if features is not None else X
        model, metrics = await asyncio.to_thread(_fit_binary_risk, rows, y, self._feature_names, self.MIN_TRAINING_EXAMPLES,
                                                   kwargs.get("training_split"), kwargs.get("calibration_splits"))
        self._model = model
        return metrics

    async def predict(self, X: Any, return_probabilities: bool = False, **kwargs: Any) -> tuple[list[Any], Any]:
        if not isinstance(X, list) or not 1 <= len(X) <= 100:
            raise ValueError("1-100 real entity feature rows required")
        _vectorize(X, self._feature_names)
        results = [await self.predict_structured(deal_features=row, **{key: value for key, value in kwargs.items()
                          if key not in {"features", "ticket_features", "deal_features"}}) for row in X]
        return results, None

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        org_id = str(kwargs.get("org_id") or "")
        settings = kwargs.get("settings") or get_settings()
        features = kwargs.get("deal_features") or kwargs.get("features") or {}
        if self._model is None:
            count = await self._count_labeled_deals(org_id, settings) if org_id else 0
            return {
                "status": "not_trained",
                "model": "deal_loss_scorer",
                "risk_score": 0.0,
                "data_gate": {
                    "current": count,
                    "required": MIN_DEAL_LOSS_LABELS,
                    "met": count >= MIN_DEAL_LOSS_LABELS,
                },
                "reason": f"Train after {MIN_DEAL_LOSS_LABELS}+ measured deal outcomes exist.",
                "advisory_only": True,
            }
        vector = _vectorize([features], self._feature_names)
        proba = float(self._model.predict_proba(vector)[0][1])
        level = "high" if proba >= 0.6 else "medium" if proba >= 0.35 else "low"
        return {
            "status": "ok",
            "model": "deal_loss_scorer",
            "loss_probability": round(proba, 4),
            "risk_score": round(proba, 4),
            "risk_level": level,
            "confidence": round(max(proba, 1.0 - proba), 4),
            "advisory_only": True,
        }

    async def _count_labeled_deals(self, org_id: str, settings: Settings) -> int:
        from app.ml.bound_training_data import collect_bound_records
        try:
            rows = await asyncio.to_thread(collect_bound_records, org_id, "deal_loss_scorer", settings, include_inputs=False)
            return len(rows)
        except Exception:
            return 0

    def save(self) -> bytes:
        if self._model is None:
            raise ValueError("Untrained risk model cannot be serialized as a valid artifact")
        return pickle.dumps({"model": self._model, "feature_names": self._feature_names})

    def load(self, data: bytes) -> None:
        self._model, self._feature_names = _load_risk_artifact(data, DEAL_FEATURE_KEYS)


class CapacityForecaster(BaseMLModel):
    model_type = ModelType.REGRESSOR
    catalog_status = ModelStatus.TRAINED
    advisory_only = True
    MIN_TRAINING_EXAMPLES = MIN_CAPACITY_SERIES

    def __init__(self) -> None:
        self._series: list[float] = []
        self._fitted = False

    async def train(
        self,
        X: np.ndarray | list[dict],
        y: np.ndarray | list[float] | None = None,
        *,
        time_series: list[dict] | None = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        _ = kwargs
        rows = time_series or (list(X) if isinstance(X, list) else [])
        values = [float(r.get("value", r.get("metric_value", r.get("after_value", 0)))) for r in rows if r]
        if y is not None and not values:
            values = [float(v) for v in y]
        if len(values) < self.MIN_TRAINING_EXAMPLES:
            raise ValueError(f"Need at least {self.MIN_TRAINING_EXAMPLES} observations, got {len(values)}")
        self._series = values
        self._fitted = True
        holdout = max(3, len(values) // 5)
        train_vals = values[:-holdout]
        test_vals = values[-holdout:]
        baseline = sum(train_vals) / len(train_vals)
        mae = mean_absolute_error(test_vals, [baseline] * len(test_vals))
        return ModelMetrics(
            mae=mae,
            training_samples=len(train_vals),
            validation_samples=len(test_vals),
        )

    async def predict(
        self,
        X: np.ndarray | list[dict],
        return_probabilities: bool = False,
        **kwargs: Any,
    ) -> tuple[list[Any], list[dict[str, float]] | None]:
        _ = X, return_probabilities, kwargs
        structured = await self.predict_structured(**kwargs)
        return [structured], None

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        org_id = str(kwargs.get("org_id") or "")
        settings = kwargs.get("settings") or get_settings()
        horizon = int(kwargs.get("horizon_days") or 7)
        if not self._fitted or not self._series:
            count = await self._count_capacity_series(org_id, settings) if org_id else 0
            return {
                "status": "not_trained",
                "model": "capacity_forecaster",
                "data_gate": {
                    "current": count,
                    "required": MIN_CAPACITY_SERIES,
                    "met": count >= MIN_CAPACITY_SERIES,
                },
                "reason": f"Train after {MIN_CAPACITY_SERIES}+ daily capacity observations exist.",
                "advisory_only": True,
            }
        recent = self._series[-7:] if len(self._series) >= 7 else self._series
        baseline = sum(recent) / len(recent)
        trend = (recent[-1] - recent[0]) / max(len(recent) - 1, 1)
        forecast = [max(0.0, baseline + trend * day) for day in range(1, horizon + 1)]
        return {
            "status": "ok",
            "model": "capacity_forecaster",
            "forecast_values": [round(v, 2) for v in forecast],
            "baseline_daily_volume": round(baseline, 2),
            "confidence_interval": {
                "low": round(baseline * 0.85, 2),
                "high": round(baseline * 1.15, 2),
            },
            "risk_score": round(min(1.0, max(forecast) / max(baseline, 1.0) - 1.0), 4),
            "advisory_only": True,
        }

    async def _count_capacity_series(self, org_id: str, settings: Settings) -> int:
        client = get_supabase_client(settings)
        try:
            resp = (
                client.table("agent_action_outcomes")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("metric_name", "ticket_volume")
                .execute()
            )
            return int(resp.count or 0)
        except Exception:  # noqa: BLE001
            return 0

    def save(self) -> bytes:
        return pickle.dumps({"series": self._series, "fitted": self._fitted})

    def load(self, data: bytes) -> None:
        loaded = pickle.loads(data)
        self._series = loaded.get("series", [])
        self._fitted = bool(loaded.get("fitted"))

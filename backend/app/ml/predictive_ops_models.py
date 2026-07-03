"""Predictive ops models — org-scoped training from agent_action_outcomes."""
from __future__ import annotations

import pickle
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, mean_absolute_error, roc_auc_score

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


def _vectorize(rows: list[dict], keys: tuple[str, ...]) -> np.ndarray:
    return np.array([[float(row.get(k) or 0.0) for k in keys] for row in rows])


class SlaBreachPredictor(BaseMLModel):
    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.TRAINED
    advisory_only = True
    MIN_TRAINING_EXAMPLES = MIN_SLA_TICKET_SAMPLES

    def __init__(self) -> None:
        self._model: GradientBoostingClassifier | LogisticRegression | None = None
        self._feature_names = list(SLA_FEATURE_KEYS)

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
            raise ValueError(f"Need at least {self.MIN_TRAINING_EXAMPLES} examples, got {len(rows)}")
        if y is None:
            raise ValueError("Labels required for SlaBreachPredictor.train")
        labels = np.array([1 if bool(v) else 0 for v in y])
        matrix = _vectorize(rows, self._feature_names)
        split = max(1, int(len(matrix) * 0.8))
        x_train, x_test = matrix[:split], matrix[split:]
        y_train, y_test = labels[:split], labels[split:]
        try:
            model: GradientBoostingClassifier | LogisticRegression = GradientBoostingClassifier(random_state=42)
            model.fit(x_train, y_train)
        except Exception:  # noqa: BLE001
            model = LogisticRegression(max_iter=1000)
            model.fit(x_train, y_train)
        self._model = model
        y_pred = model.predict(x_test) if len(x_test) else y_train
        y_proba = model.predict_proba(x_test)[:, 1] if len(x_test) else model.predict_proba(x_train)[:, 1]
        auc = roc_auc_score(y_test, y_proba) if len(set(y_test)) > 1 and len(x_test) else None
        return ModelMetrics(
            accuracy=accuracy_score(y_test, y_pred) if len(x_test) else 1.0,
            auc_roc=auc,
            training_samples=len(x_train),
            validation_samples=len(x_test),
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
            "confidence": round(min(1.0, proba if level == "high" else 1.0 - proba), 4),
            "drivers": [k.replace("_", " ") for k in self._feature_names if float(features.get(k) or 0) > 0],
            "advisory_only": True,
        }

    async def _count_ticket_signals(self, org_id: str, settings: Settings) -> int:
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
        return pickle.dumps({"model": self._model, "feature_names": self._feature_names})

    def load(self, data: bytes) -> None:
        loaded = pickle.loads(data)
        self._model = loaded["model"]
        self._feature_names = loaded.get("feature_names", list(SLA_FEATURE_KEYS))


class DealLossScorer(BaseMLModel):
    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.TRAINED
    advisory_only = True
    MIN_TRAINING_EXAMPLES = MIN_DEAL_LOSS_LABELS

    def __init__(self) -> None:
        self._model: GradientBoostingClassifier | LogisticRegression | None = None
        self._feature_names = list(DEAL_FEATURE_KEYS)

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
            raise ValueError(f"Need at least {self.MIN_TRAINING_EXAMPLES} examples, got {len(rows)}")
        if y is None:
            raise ValueError("Labels required for DealLossScorer.train")
        labels = np.array([1 if bool(v) else 0 for v in y])
        matrix = _vectorize(rows, self._feature_names)
        split = max(1, int(len(matrix) * 0.8))
        x_train, x_test = matrix[:split], matrix[split:]
        y_train, y_test = labels[:split], labels[split:]
        model: GradientBoostingClassifier | LogisticRegression = GradientBoostingClassifier(random_state=42)
        model.fit(x_train, y_train)
        self._model = model
        y_pred = model.predict(x_test) if len(x_test) else y_train
        y_proba = model.predict_proba(x_test)[:, 1] if len(x_test) else model.predict_proba(x_train)[:, 1]
        return ModelMetrics(
            accuracy=accuracy_score(y_test, y_pred) if len(x_test) else 1.0,
            auc_roc=roc_auc_score(y_test, y_proba) if len(set(y_test)) > 1 and len(x_test) else None,
            training_samples=len(x_train),
            validation_samples=len(x_test),
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
            "confidence": round(min(1.0, proba if level == "high" else 1.0 - proba), 4),
            "advisory_only": True,
        }

    async def _count_labeled_deals(self, org_id: str, settings: Settings) -> int:
        client = get_supabase_client(settings)
        try:
            resp = (
                client.table("agent_action_outcomes")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("target_entity_type", "deal")
                .not_.is_("measured_at", "null")
                .execute()
            )
            return int(resp.count or 0)
        except Exception:  # noqa: BLE001
            return 0

    def save(self) -> bytes:
        return pickle.dumps({"model": self._model, "feature_names": self._feature_names})

    def load(self, data: bytes) -> None:
        loaded = pickle.loads(data)
        self._model = loaded["model"]
        self._feature_names = loaded.get("feature_names", list(DEAL_FEATURE_KEYS))


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

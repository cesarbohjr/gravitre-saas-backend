"""v4 memory promotion likelihood scorer from resolved promotion candidates."""
from __future__ import annotations

import pickle
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split

from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus, ModelType

PROMOTION_POSITIVE_STATUSES = frozenset({"approved", "auto_promoted", "written"})
PROMOTION_NEGATIVE_STATUSES = frozenset({"rejected", "rolled_back", "expired"})

CANDIDATE_TYPE_INDEX = {
    "glossary": 0,
    "workflow_pattern": 1,
    "successful_response": 2,
}
MEMORY_CATEGORY_INDEX = {
    "fact": 0,
    "preference": 1,
    "pattern": 2,
    "rule": 3,
}

FEATURE_NAMES = [
    "frequency",
    "department_count",
    "content_length",
    "type_glossary",
    "type_workflow_pattern",
    "type_successful_response",
    "cat_fact",
    "cat_preference",
    "cat_pattern",
    "cat_rule",
]


class MemoryPromotionScorer(BaseMLModel):
    """
    Learns promotion approval patterns from v4 audit history.
    Advisory only — assists human/auto promotion gates, never writes memories alone.
    """

    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.TRAINED
    advisory_only = True
    MIN_TRAINING_EXAMPLES = 15

    def __init__(self) -> None:
        self.model: LogisticRegression | None = None

    @staticmethod
    def features_from_candidate(row: dict[str, Any]) -> dict[str, float]:
        candidate_type = str(row.get("candidate_type") or "successful_response")
        memory_category = str(row.get("memory_category") or "fact")
        content = str(row.get("content") or "")
        features: dict[str, float] = {
            "frequency": float(row.get("frequency") or 0),
            "department_count": float(row.get("department_count") or 0),
            "content_length": float(len(content)),
        }
        for name in CANDIDATE_TYPE_INDEX:
            features[f"type_{name}"] = 1.0 if candidate_type == name else 0.0
        for name in MEMORY_CATEGORY_INDEX:
            features[f"cat_{name}"] = 1.0 if memory_category == name else 0.0
        return features

    @staticmethod
    def label_from_status(status: str | None) -> int | None:
        normalized = str(status or "").strip().lower()
        if normalized in PROMOTION_POSITIVE_STATUSES:
            return 1
        if normalized in PROMOTION_NEGATIVE_STATUSES:
            return 0
        return None

    async def train(
        self,
        X: np.ndarray | list[dict] | None = None,
        y: np.ndarray | list[str] | list[float] | None = None,
        *,
        candidates: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        _ = kwargs
        rows = candidates or (list(X) if isinstance(X, list) else [])
        feature_rows: list[dict[str, float]] = []
        labels: list[int] = []
        for row in rows:
            label = self.label_from_status(row.get("status"))
            if label is None:
                continue
            feature_rows.append(self.features_from_candidate(row))
            labels.append(label)
        if len(feature_rows) < self.MIN_TRAINING_EXAMPLES:
            raise ValueError(
                f"Need at least {self.MIN_TRAINING_EXAMPLES} resolved candidates, got {len(feature_rows)}"
            )
        matrix = np.array([[float(item.get(name) or 0.0) for name in FEATURE_NAMES] for item in feature_rows])
        y_arr = np.array(labels, dtype=int)
        x_train, x_test, y_train, y_test = train_test_split(
            matrix,
            y_arr,
            test_size=0.2,
            random_state=42,
            stratify=y_arr if len(set(y_arr)) > 1 else None,
        )
        self.model = LogisticRegression(max_iter=1000, class_weight="balanced")
        self.model.fit(x_train, y_train)
        predictions = self.model.predict(x_test)
        metrics = ModelMetrics(
            accuracy=float(accuracy_score(y_test, predictions)),
            f1_score=float(f1_score(y_test, predictions, zero_division=0)),
            training_samples=len(x_train),
            validation_samples=len(x_test),
            custom_metrics={
                "positive_rate": round(float(y_arr.mean()), 4),
                "feature_count": float(len(FEATURE_NAMES)),
            },
        )
        if len(set(y_test)) > 1:
            try:
                probabilities = self.model.predict_proba(x_test)[:, 1]
                metrics.auc_roc = float(roc_auc_score(y_test, probabilities))
            except ValueError:
                pass
        return metrics

    async def predict(
        self,
        X: np.ndarray | list[dict],
        return_probabilities: bool = False,
        **kwargs: Any,
    ) -> tuple[list[Any], list[dict[str, float]] | None]:
        _ = kwargs
        rows = list(X) if isinstance(X, list) else []
        if not rows or self.model is None:
            return [], None
        matrix = np.array(
            [
                [float(self.features_from_candidate(row).get(name) or 0.0) for name in FEATURE_NAMES]
                for row in rows
            ]
        )
        preds = self.model.predict(matrix).tolist()
        probs = None
        if return_probabilities:
            prob_values = self.model.predict_proba(matrix)
            probs = [{"approve": float(row[1]), "reject": float(row[0])} for row in prob_values]
        return preds, probs

    async def score_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        if self.model is None:
            return {
                "status": "not_trained",
                "advisory_only": True,
                "message": "Insufficient resolved promotion history for this org.",
            }
        features = self.features_from_candidate(candidate)
        matrix = np.array([[float(features.get(name) or 0.0) for name in FEATURE_NAMES]])
        probability = float(self.model.predict_proba(matrix)[0][1])
        return {
            "status": "ok",
            "advisory_only": True,
            "approval_probability": round(probability, 4),
            "recommendation": "likely_approve" if probability >= 0.6 else "review",
        }

    def save(self) -> bytes:
        return pickle.dumps({"model": self.model, "feature_names": FEATURE_NAMES})

    def load(self, data: bytes) -> None:
        loaded = pickle.loads(data)
        self.model = loaded.get("model")

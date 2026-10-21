"""Outcome-trained action recommendation; execution stays in the existing ReAct engine."""
from __future__ import annotations

import pickle
from typing import Any

import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score

from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus, ModelType


class AgentPlanningModel(BaseMLModel):
    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.READY
    advisory_only = True
    MIN_TRAINING_EXAMPLES = 100

    def __init__(self) -> None:
        self._model: LogisticRegression | None = None
        self._vectorizer = DictVectorizer(sparse=True)

    @staticmethod
    def _rows(X: Any) -> list[dict]:
        if not isinstance(X, list) or not X:
            raise ValueError("Structured context/action rows required")
        for row in X:
            if not isinstance(row, dict) or not isinstance(row.get("action"), str) or not row["action"]:
                raise ValueError("Every trajectory requires an action")
            if any(not isinstance(value, (str, int, float)) or isinstance(value, bool)
                   or isinstance(value, (int, float)) and not np.isfinite(value) for value in row.values()):
                raise ValueError("Finite numeric or categorical trajectory features required")
        return X

    async def train(self, X: Any, y: Any = None, **kwargs: Any) -> ModelMetrics:
        rows = self._rows(X)
        if len(rows) < self.MIN_TRAINING_EXAMPLES:
            raise ValueError("100 measured action outcomes required")
        if not isinstance(y, list) or len(y) != len(rows) or any(type(v) not in {int, bool} or v not in {0, 1} for v in y):
            raise ValueError("Explicit measured binary outcomes required")
        split = int(len(rows)*.8)
        if len(set(y[:split])) != 2 or len(set(y[split:])) != 2:
            raise ValueError("Both outcome classes required in training and temporal holdout")
        vectorizer = DictVectorizer(sparse=True)
        matrix = vectorizer.fit_transform(rows[:split])
        model = LogisticRegression(max_iter=1000, random_state=42).fit(matrix, y[:split])
        test = vectorizer.transform(rows[split:])
        probability = model.predict_proba(test)[:, 1]
        auc = float(roc_auc_score(y[split:], probability))
        if auc <= .5:
            raise ValueError("Planning predictor did not beat chance on temporal holdout")
        self._model, self._vectorizer = model, vectorizer
        return ModelMetrics(auc_roc=auc, accuracy=float(accuracy_score(y[split:], model.predict(test))),
                            training_samples=split, validation_samples=len(rows)-split)

    async def predict(self, X: Any, return_probabilities: bool = False, **kwargs: Any) -> tuple[list[Any], Any]:
        if self._model is None:
            raise ValueError("Validated planning artifact required")
        rows = self._rows(X)
        known_actions = {name[len("action="):] for name in self._vectorizer.get_feature_names_out()
                         if name.startswith("action=")}
        if any(row["action"] not in known_actions for row in rows):
            raise ValueError("Candidate action was not represented in measured training history")
        matrix = self._vectorizer.transform(rows)
        probability = self._model.predict_proba(matrix)[:, 1]
        return probability.tolist(), None

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        if self._model is None:
            return {"status": "dormant", "model": "agentic_planning", "reason": "validated_artifact_required"}
        rows = self._rows(kwargs.get("inputs"))
        probabilities, _ = await self.predict(rows)
        return {"status": "ok", "model": "agentic_planning", "advisory_only": True,
                "recommendations": sorted([{"action": row["action"], "estimated_success_probability": p}
                                           for row, p in zip(rows, probabilities)],
                                          key=lambda item: -item["estimated_success_probability"]),
                "note": "Ranks provided candidates only; existing authorization and execution gates still apply."}

    def save(self) -> bytes:
        if self._model is None:
            raise ValueError("Untrained planning model")
        return pickle.dumps({"schema": 1, "model": self._model, "vectorizer": self._vectorizer})

    def load(self, data: bytes) -> None:
        artifact = pickle.loads(data)
        if not isinstance(artifact, dict) or artifact.get("schema") != 1 or not isinstance(artifact.get("model"), LogisticRegression):
            raise ValueError("Invalid planning artifact")
        self._model, self._vectorizer = artifact["model"], artifact["vectorizer"]

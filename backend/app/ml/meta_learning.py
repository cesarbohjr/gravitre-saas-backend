"""Organization-local first-order meta-learning across explicitly labeled tasks.

Reptile learns an initialization, then adapts it to a provided support set.
Cross-organization transfer is intentionally unsupported: local task adaptation
needs no federated permissions and cannot authorize sharing tenant examples.
"""
from __future__ import annotations

import asyncio
import io
from typing import Any

import numpy as np
from scipy.special import expit
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score

from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus, ModelType


class MetaLearningAdaptor(BaseMLModel):
    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.READY
    advisory_only = True

    def __init__(self) -> None:
        self._prior: np.ndarray | None = None

    @staticmethod
    def _samples(rows: Any) -> tuple[np.ndarray, np.ndarray, set[str]]:
        if not isinstance(rows, list) or not 2 <= len(rows) <= 100:
            raise ValueError("2-100 explicitly labeled support/query examples required")
        ids = [row.get("id") for row in rows if isinstance(row, dict)]
        if len(ids) != len(rows) or any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
            raise ValueError("Distinct example identifiers required")
        features = np.asarray([row.get("features") for row in rows], dtype=float)
        labels = [row.get("label") for row in rows]
        if (features.ndim != 2 or not 1 <= features.shape[1] <= 32 or not np.isfinite(features).all()
                or np.any(np.abs(features) > 10) or any(type(v) not in {int, bool} or v not in {0, 1} for v in labels)):
            raise ValueError("Finite, pre-normalized features in [-10,10] and binary labels required")
        return np.column_stack([features, np.ones(len(rows))]), np.asarray(labels, dtype=float), set(ids)

    @staticmethod
    def _adapt(prior: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        if x.shape[1] != len(prior):
            raise ValueError("Task feature schema does not match artifact")
        weights = prior.copy()
        for _ in range(5):
            weights -= .05 * (x.T @ (expit(x @ weights)-y) / len(y) + .001*weights)
        return weights

    def _fit(self, episodes: Any) -> ModelMetrics:
        if not isinstance(episodes, list) or not 20 <= len(episodes) <= 1000:
            raise ValueError("20-1000 independent task episodes required")
        tasks, task_ids, example_ids = [], set(), set()
        for episode in episodes:
            if not isinstance(episode, dict) or not isinstance(episode.get("task_id"), str) or not episode["task_id"] or episode["task_id"] in task_ids:
                raise ValueError("Distinct tenant-local task identifiers required")
            support_x, support_y, support_ids = self._samples(episode.get("support"))
            query_x, query_y, query_ids = self._samples(episode.get("query"))
            if support_ids & query_ids or example_ids & (support_ids | query_ids):
                raise ValueError("Support, query and task examples must be disjoint")
            if support_x.shape[1] != query_x.shape[1] or tasks and support_x.shape[1] != tasks[0][0].shape[1]:
                raise ValueError("One feature schema required across tasks")
            task_ids.add(episode["task_id"])
            example_ids.update(support_ids | query_ids)
            tasks.append((support_x, support_y, query_x, query_y))
        # Held-out tasks are never used to update the initialization.
        split = int(len(tasks)*.8)
        prior = np.zeros(tasks[0][0].shape[1])
        for step in range(500):
            sx, sy, qx, qy = tasks[step % split]
            x, y = np.concatenate([sx, qx]), np.concatenate([sy, qy])
            prior += .1 * (self._adapt(prior, x, y)-prior)
        predictions, baseline, actual = [], [], []
        for sx, sy, qx, qy in tasks[split:]:
            predictions.extend(expit(qx @ self._adapt(prior, sx, sy)))
            baseline.extend(expit(qx @ self._adapt(np.zeros_like(prior), sx, sy)))
            actual.extend(qy)
        if len(set(actual)) != 2:
            raise ValueError("Both classes required in held-out task queries")
        auc = float(roc_auc_score(actual, predictions))
        loss, baseline_loss = float(log_loss(actual, predictions)), float(log_loss(actual, baseline))
        if auc <= .5 or loss >= baseline_loss or not np.isfinite(prior).all():
            raise ValueError("Adaptation must beat chance and support-only initialization on held-out tasks")
        self._prior = prior
        return ModelMetrics(auc_roc=auc, accuracy=float(accuracy_score(actual, np.asarray(predictions) >= .5)),
                            training_samples=sum(len(t[1])+len(t[3]) for t in tasks[:split]), validation_samples=len(actual),
                            custom_metrics={"algorithm": "first_order_reptile", "held_out_tasks": len(tasks)-split,
                                            "query_log_loss": loss, "support_only_log_loss": baseline_loss,
                                            "cross_org_training": False})

    async def train(self, X: Any, y: Any = None, **kwargs: Any) -> ModelMetrics:
        return await asyncio.to_thread(self._fit, X)

    async def predict(self, X: Any, return_probabilities: bool = False, **kwargs: Any) -> tuple[list[Any], Any]:
        if self._prior is None:
            raise ValueError("Validated meta-learning artifact required")
        if not isinstance(X, list) or not 1 <= len(X) <= 100:
            raise ValueError("1-100 adaptation tasks required")
        results = []
        for episode in X:
            sx, sy, ids = self._samples(episode.get("support"))
            query = np.asarray(episode.get("query_features"), dtype=float)
            if (query.ndim != 2 or not 1 <= len(query) <= 100 or query.shape[1] != len(self._prior)-1
                    or not np.isfinite(query).all() or np.any(np.abs(query) > 10)):
                raise ValueError("Bounded query features matching task schema required")
            qx = np.column_stack([query, np.ones(len(query))])
            results.append(expit(qx @ self._adapt(self._prior, sx, sy)).tolist())
        return results, None

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        if self._prior is None:
            return {"status": "dormant", "reason": "validated_local_task_artifact_required", "advisory_only": True}
        predictions, _ = await self.predict(kwargs.get("inputs"))
        return {"status": "ok", "predictions": predictions, "advisory_only": True,
                "scope": "Organization-local task adaptation; no cross-organization transfer"}

    def save(self) -> bytes:
        if self._prior is None:
            raise ValueError("Untrained meta-learning model")
        buffer = io.BytesIO()
        np.savez_compressed(buffer, schema=np.array([1]), prior=self._prior)
        return buffer.getvalue()

    def load(self, data: bytes) -> None:
        if len(data) > 10000:
            raise ValueError("Meta-learning artifact exceeds bounded size")
        with np.load(io.BytesIO(data), allow_pickle=False) as archive:
            if set(archive.files) != {"schema", "prior"} or archive["schema"].tolist() != [1]:
                raise ValueError("Invalid meta-learning artifact")
            prior = archive["prior"].copy()
        if prior.ndim != 1 or not 2 <= len(prior) <= 33 or not np.isfinite(prior).all():
            raise ValueError("Invalid meta-learning prior")
        self._prior = prior

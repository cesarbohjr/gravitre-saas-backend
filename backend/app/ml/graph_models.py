"""Bounded, org-local graph convolution for labeled relationship outcomes.

CPU NumPy implementation reuses the catalog/registry. No GPU or new engine.
Graph structure is context, never a manufactured outcome label. Callers must
supply independently measured labels and chronological, disjoint graph snapshots.
"""
from __future__ import annotations

import asyncio
import io
from datetime import datetime
from typing import Any

import numpy as np
from scipy.special import expit
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score

from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus, ModelType


class GraphNeuralNetworkScorer(BaseMLModel):
    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.READY
    advisory_only = True
    MIN_TRAINING_EXAMPLES = 100

    def __init__(self) -> None:
        self._weights: dict[str, np.ndarray] | None = None

    @staticmethod
    def _aggregate(row: Any) -> np.ndarray:
        if not isinstance(row, dict):
            raise ValueError("Graph object required")
        features = np.asarray(row.get("node_features"), dtype=float)
        if features.ndim != 2 or not 2 <= len(features) <= 512 or not 1 <= features.shape[1] <= 32 or not np.isfinite(features).all():
            raise ValueError("2-512 nodes with 1-32 finite numeric features required")
        source, target = row.get("source"), row.get("target")
        if any(type(v) is not int or not 0 <= v < len(features) for v in (source, target)) or source == target:
            raise ValueError("Distinct in-graph source and target required")
        edges = row.get("edges")
        if not isinstance(edges, list) or len(edges) > 10000:
            raise ValueError("At most 10000 graph edges required")
        neighbors = [set([i]) for i in range(len(features))]
        for edge in edges:
            if not isinstance(edge, (list, tuple)) or len(edge) != 2 or any(type(v) is not int or not 0 <= v < len(features) for v in edge):
                raise ValueError("Edge endpoints must index graph nodes")
            a, b = edge
            if {a, b} == {source, target}:
                raise ValueError("Candidate relationship must be withheld from message-passing context")
            neighbors[a].add(b)
            neighbors[b].add(a)
        # Shared learned projection after normalized neighbor aggregation: a
        # one-layer graph convolution, followed by a directed pair classifier.
        return np.stack([features[sorted(neighbors[i])].mean(axis=0) for i in (source, target)])

    @classmethod
    def _matrix(cls, X: Any) -> np.ndarray:
        if not isinstance(X, list) or not 1 <= len(X) <= 2000:
            raise ValueError("1-2000 graph examples required")
        return np.stack([cls._aggregate(row) for row in X])

    @staticmethod
    def _forward(x: np.ndarray, w: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        z = np.einsum("npf,fh->nph", x, w["projection"]) + w["bias"]
        hidden = np.maximum(z, 0)
        pairs = hidden.reshape(len(x), -1)
        return expit(pairs @ w["output"] + w["intercept"]), z, pairs

    def _fit(self, X: Any, y: Any) -> ModelMetrics:
        matrix = self._matrix(X)
        if len(matrix) < self.MIN_TRAINING_EXAMPLES:
            raise ValueError("100 independently labeled graph examples required")
        if not isinstance(y, list) or len(y) != len(X) or any(type(v) not in {int, bool} or v not in {0, 1} for v in y):
            raise ValueError("Independent measured binary relationship outcomes required")
        times, ids = [], []
        for row in X:
            measured = datetime.fromisoformat(str(row.get("observed_at", "")).replace("Z", "+00:00"))
            if measured.tzinfo is None or not isinstance(row.get("graph_id"), str) or not row["graph_id"]:
                raise ValueError("Timestamp with timezone and graph_id required")
            times.append(measured)
            ids.append(row["graph_id"])
        if times != sorted(times):
            raise ValueError("Chronological graph examples required")
        split = int(len(X) * .8)
        if set(ids[:split]) & set(ids[split:]):
            raise ValueError("Training and temporal holdout graphs must be disjoint")
        if len(set(y[:split])) != 2 or len(set(y[split:])) != 2:
            raise ValueError("Both classes required in training and holdout")
        mean = matrix[:split].mean(axis=(0, 1))
        scale = matrix[:split].std(axis=(0, 1))
        scale[scale < 1e-8] = 1
        normalized = (matrix - mean) / scale
        train, target = normalized[:split], np.asarray(y[:split], dtype=float)
        rng = np.random.default_rng(42)
        w = {"projection": rng.normal(0, .2, (matrix.shape[2], 16)), "bias": np.zeros(16),
             "output": rng.normal(0, .1, 32), "intercept": np.zeros(1), "mean": mean, "scale": scale}
        for _ in range(400):
            probability, z, pairs = self._forward(train, w)
            error = (probability-target) / split
            hidden_gradient = (error[:, None] * w["output"]).reshape(split, 2, 16) * (z > 0)
            projection_gradient = np.einsum("npf,nph->fh", train, hidden_gradient)
            w["projection"] -= .05 * (projection_gradient + .001*w["projection"])
            w["bias"] -= .05 * hidden_gradient.sum(axis=(0, 1))
            w["output"] -= .05 * (pairs.T @ error + .001*w["output"])
            w["intercept"] -= .05 * error.sum()
        probabilities, _, _ = self._forward(normalized[split:], w)
        auc = float(roc_auc_score(y[split:], probabilities))
        loss = float(log_loss(y[split:], probabilities))
        baseline_loss = float(log_loss(y[split:], np.full(len(y)-split, target.mean())))
        if auc <= .5 or loss >= baseline_loss or not all(np.isfinite(value).all() for value in w.values()):
            raise ValueError("Graph predictor did not beat prior baseline on temporal holdout")
        self._weights = w
        return ModelMetrics(auc_roc=auc, accuracy=float(accuracy_score(y[split:], probabilities >= .5)),
                            training_samples=split, validation_samples=len(y)-split,
                            custom_metrics={"algorithm": "mean_graph_convolution", "holdout_log_loss": loss,
                                            "prior_log_loss": baseline_loss, "cross_org_training": False})

    async def train(self, X: Any, y: Any = None, **kwargs: Any) -> ModelMetrics:
        return await asyncio.to_thread(self._fit, X, y)

    def _predict(self, X: Any, return_probabilities: bool = False) -> tuple[list[Any], Any]:
        if self._weights is None:
            raise ValueError("Validated graph artifact required")
        matrix = self._matrix(X)
        w = self._weights
        if matrix.shape[2] != len(w["mean"]):
            raise ValueError("Graph feature schema does not match artifact")
        probability, _, _ = self._forward((matrix-w["mean"])/w["scale"], w)
        return probability.tolist(), ([{"positive": float(p), "negative": float(1-p)} for p in probability]
                                       if return_probabilities else None)

    async def predict(self, X: Any, return_probabilities: bool = False, **kwargs: Any) -> tuple[list[Any], Any]:
        # Sparse edge parsing can be CPU-bound; keep shared text/voice responsive.
        return await asyncio.to_thread(self._predict, X, return_probabilities)

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        if self._weights is None:
            return {"status": "dormant", "model": "graph_neural_network", "reason": "validated_graph_artifact_required",
                    "fallback": "postgres_confidence_traversal", "advisory_only": True}
        rows = kwargs.get("inputs")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
            raise ValueError("1-100 candidate graphs required for inference")
        predictions, probabilities = await self.predict(rows, return_probabilities=True)
        return {"status": "ok", "predictions": predictions, "probabilities": probabilities,
                "advisory_only": True, "scope": "Provided graph features and measured training target only"}

    def save(self) -> bytes:
        if self._weights is None:
            raise ValueError("Untrained graph model")
        buffer = io.BytesIO()
        np.savez_compressed(buffer, schema=np.array([1]), **self._weights)
        return buffer.getvalue()

    def load(self, data: bytes) -> None:
        if len(data) > 1000000:
            raise ValueError("Graph artifact exceeds bounded model size")
        with np.load(io.BytesIO(data), allow_pickle=False) as archive:
            if set(archive.files) != {"schema", "projection", "bias", "output", "intercept", "mean", "scale"} or archive["schema"].tolist() != [1]:
                raise ValueError("Invalid graph artifact schema")
            w = {name: archive[name].copy() for name in archive.files if name != "schema"}
        features = len(w["mean"])
        if (not 1 <= features <= 32 or w["mean"].shape != (features,) or w["scale"].shape != (features,)
                or w["projection"].shape != (features, 16) or w["bias"].shape != (16,)
                or w["output"].shape != (32,) or w["intercept"].shape != (1,)
                or not all(np.isfinite(value).all() for value in w.values()) or np.any(w["scale"] <= 0)):
            raise ValueError("Invalid graph artifact weights")
        self._weights = w

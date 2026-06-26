"""Query clustering over normalized query embeddings (v3)."""
from __future__ import annotations

import pickle
from typing import Any

import numpy as np
from sklearn.cluster import HDBSCAN

from app.core.logging import get_logger
from app.ml.base import BaseMLModel, ModelMetrics, ModelType

logger = get_logger(__name__)


class QueryClusterer(BaseMLModel):
    """HDBSCAN over query embedding vectors for recurring theme discovery."""

    model_type = ModelType.EMBEDDING

    def __init__(self, min_cluster_size: int = 3, min_samples: int = 2):
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.model: HDBSCAN | None = None
        self._embeddings: np.ndarray | None = None
        self._queries: list[str] = []
        self._labels: list[int] = []

    async def train(
        self,
        X: np.ndarray | list[dict] | None = None,
        y: np.ndarray | list[str] | None = None,
        *,
        embeddings: list[list[float]] | None = None,
        normalized_queries: list[str] | None = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        _ = X, y, kwargs
        texts = normalized_queries or []
        if embeddings is None or not embeddings:
            raise ValueError("embeddings required for QueryClusterer.train")
        if len(embeddings) != len(texts):
            raise ValueError("embeddings and normalized_queries length mismatch")
        matrix = np.array(embeddings, dtype=float)
        self._embeddings = matrix
        self._queries = list(texts)
        self.model = HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
            metric="euclidean",
        )
        self.model.fit(matrix)
        self._labels = [int(x) for x in self.model.labels_]
        n_clusters = len({label for label in self._labels if label >= 0})
        noise = sum(1 for label in self._labels if label < 0)
        return ModelMetrics(
            training_samples=len(texts),
            custom_metrics={
                "n_clusters": n_clusters,
                "noise_points": noise,
                "algorithm": "hdbscan",
            },
        )

    async def predict(
        self,
        X: np.ndarray | list[dict],
        return_probabilities: bool = False,
        **kwargs: Any,
    ) -> tuple[list[Any], list[dict[str, float]] | None]:
        _ = kwargs
        raise NotImplementedError("Use assign_clusters() for query assignment")

    async def assign_clusters(
        self,
        embeddings: list[list[float]],
        queries: list[str],
    ) -> list[dict[str, Any]]:
        """Assign cluster_id per query using nearest trained cluster centroid."""
        if self._embeddings is None or not self._labels:
            return [{"query": q, "cluster_id": -1} for q in queries]

        centroids: dict[int, np.ndarray] = {}
        counts: dict[int, int] = {}
        for idx, label in enumerate(self._labels):
            if label < 0:
                continue
            vec = self._embeddings[idx]
            if label not in centroids:
                centroids[label] = vec.copy()
                counts[label] = 1
            else:
                centroids[label] = centroids[label] + vec
                counts[label] += 1
        for label, total in counts.items():
            centroids[label] = centroids[label] / total

        results: list[dict[str, Any]] = []
        for query, emb in zip(queries, embeddings):
            vec = np.array(emb, dtype=float)
            if not centroids:
                results.append({"query": query, "cluster_id": -1})
                continue
            best_label = min(
                centroids.keys(),
                key=lambda lbl: float(np.linalg.norm(vec - centroids[lbl])),
            )
            results.append({"query": query, "cluster_id": int(best_label)})
        return results

    def cluster_members(self) -> dict[int, list[str]]:
        grouped: dict[int, list[str]] = {}
        for query, label in zip(self._queries, self._labels):
            if label < 0:
                continue
            grouped.setdefault(label, []).append(query)
        return grouped

    def save(self) -> bytes:
        return pickle.dumps(
            {
                "min_cluster_size": self.min_cluster_size,
                "min_samples": self.min_samples,
                "model": self.model,
                "embeddings": self._embeddings,
                "queries": self._queries,
                "labels": self._labels,
            }
        )

    def load(self, data: bytes) -> None:
        loaded = pickle.loads(data)
        self.min_cluster_size = loaded["min_cluster_size"]
        self.min_samples = loaded["min_samples"]
        self.model = loaded["model"]
        self._embeddings = loaded["embeddings"]
        self._queries = loaded["queries"]
        self._labels = loaded["labels"]

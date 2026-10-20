"""Org-local latent semantic embeddings; never replaces the global embedding space."""
from __future__ import annotations

import pickle
from typing import Any

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus, ModelType


class SelfSupervisedEmbeddingLearner(BaseMLModel):
    model_type = ModelType.EMBEDDING
    catalog_status = ModelStatus.READY
    MIN_DOCUMENTS = 100

    def __init__(self) -> None:
        self._vectorizer: TfidfVectorizer | None = None
        self._projection: TruncatedSVD | None = None

    @staticmethod
    def _texts(X: Any) -> list[str]:
        if not isinstance(X, list) or not X or any(not isinstance(text, str) or not text.strip() for text in X):
            raise ValueError("Nonempty document strings required")
        return X

    async def train(self, X: Any, y: Any = None, **kwargs: Any) -> ModelMetrics:
        texts = self._texts(X)
        if len(set(texts)) < self.MIN_DOCUMENTS:
            raise ValueError("100 distinct org-local documents required")
        vectorizer = TfidfVectorizer(max_features=8192, min_df=2, max_df=.98)
        matrix = vectorizer.fit_transform(texts)
        dimensions = min(64, matrix.shape[0]-1, matrix.shape[1]-1)
        if dimensions < 2:
            raise ValueError("Insufficient document vocabulary")
        projection = TruncatedSVD(n_components=dimensions, random_state=42).fit(matrix)
        self._vectorizer, self._projection = vectorizer, projection
        # Reconstruction variance is not retrieval effectiveness or a promotion metric.
        return ModelMetrics(training_samples=len(texts), custom_metrics={
            "explained_variance": float(projection.explained_variance_ratio_.sum()),
            "dimensions": dimensions, "retrieval_quality_verified": False})

    async def predict(self, X: Any, return_probabilities: bool = False, **kwargs: Any) -> tuple[list[Any], None]:
        if self._vectorizer is None or self._projection is None:
            raise ValueError("Org-local embedding artifact required")
        matrix = self._vectorizer.transform(self._texts(X))
        if np.any(matrix.getnnz(axis=1) == 0):
            raise ValueError("Input outside learned vocabulary")
        return normalize(self._projection.transform(matrix)).tolist(), None

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        if self._projection is None:
            return {"status": "dormant", "model": "self_supervised_embeddings", "reason": "validated_artifact_required"}
        embeddings, _ = await self.predict(kwargs.get("inputs"))
        return {"status": "ok", "model": "self_supervised_embeddings", "embeddings": embeddings,
                "embedding_space": "org_local_lsa", "compatible_with_global_rag_vectors": False}

    def save(self) -> bytes:
        if self._projection is None:
            raise ValueError("Untrained embedding model")
        return pickle.dumps({"schema": 1, "vectorizer": self._vectorizer, "projection": self._projection})

    def load(self, data: bytes) -> None:
        artifact = pickle.loads(data)
        if not isinstance(artifact, dict) or artifact.get("schema") != 1 or not isinstance(artifact.get("projection"), TruncatedSVD):
            raise ValueError("Invalid embedding artifact")
        self._vectorizer, self._projection = artifact["vectorizer"], artifact["projection"]

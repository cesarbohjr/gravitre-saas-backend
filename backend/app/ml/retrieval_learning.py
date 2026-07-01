"""Unified retrieval learning interface over v3/v4/v5/v7 components."""
from __future__ import annotations

from typing import Any

import numpy as np

from app.config import Settings, get_settings
from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus, ModelType
from app.ml.clustering import QueryClusterer
from app.ml.learning_to_rank import RetrievalRanker
from app.ml.source_reliability import (
    MIN_OUTCOMES_FOR_SCORING,
    RELIABILITY_WEIGHT,
    fetch_source_reliability_scores,
)
from app.workflows.repository import get_supabase_client


class RetrievalMemoryLearner(BaseMLModel):
    """
    Unified interface for Gravitre retrieval learning:
    RetrievalRanker (v7), SourceReliabilityScorer (v5), QueryClusterer (v3),
    agent_memories (v4 episodic memory via counts).
    """

    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.TRAINED
    advisory_only = False

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._ranker = RetrievalRanker()
        self._clusterer = QueryClusterer()

    async def train(
        self,
        X: np.ndarray | list[dict],
        y: np.ndarray | list[str] | list[float] | None = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        return await self._ranker.train(X, y, **kwargs)

    async def predict(
        self,
        X: np.ndarray | list[dict],
        return_probabilities: bool = False,
        **kwargs: Any,
    ) -> tuple[list[Any], list[dict[str, float]] | None]:
        org_id = kwargs.get("org_id")
        if not org_id and isinstance(X, list) and X and isinstance(X[0], dict):
            org_id = X[0].get("org_id")
        if not org_id:
            raise ValueError("org_id required for RetrievalMemoryLearner.predict")
        summary = await self.get_retrieval_quality_summary(str(org_id))
        return [summary], None

    async def train_for_org(self, org_id: str) -> dict[str, Any]:
        from app.ml.intelligence_training import train_retrieval_memory_learner

        return await train_retrieval_memory_learner(org_id, settings=self.settings)

    async def get_retrieval_quality_summary(self, org_id: str) -> dict[str, Any]:
        client = get_supabase_client(self.settings)
        reliability_scores = await fetch_source_reliability_scores(org_id, client)
        scored_sources = len(reliability_scores)
        avg_reliability = (
            round(sum(reliability_scores.values()) / scored_sources, 4) if scored_sources else None
        )
        query_rows = (
            client.table("user_query_patterns")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .execute()
        )
        query_count = int(query_rows.count or 0)
        cluster_rows = (
            client.table("org_query_clusters")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .execute()
        )
        cluster_count = int(cluster_rows.count or 0)
        memory_rows = (
            client.table("agent_memories")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .eq("status", "approved")
            .execute()
        )
        memory_count = int(memory_rows.count or 0)
        ranker_ready = scored_sources >= RetrievalRanker.MIN_TRAINING_EXAMPLES
        return {
            "status": "ok",
            "org_id": org_id,
            "source_reliability": {
                "scored_sources": scored_sources,
                "min_required": MIN_OUTCOMES_FOR_SCORING,
                "average_score": avg_reliability,
                "default_weight": RELIABILITY_WEIGHT,
                "ranker_trained": ranker_ready,
            },
            "query_clustering": {
                "logged_queries": query_count,
                "cluster_count": cluster_count,
                "min_queries_for_clustering": 40,
            },
            "agent_memories": {
                "approved_memory_count": memory_count,
            },
            "components": [
                "RetrievalRanker",
                "SourceReliabilityScorer",
                "QueryClusterer",
                "agent_memories",
            ],
        }

    def save(self) -> bytes:
        return self._ranker.save()

    def load(self, data: bytes) -> None:
        self._ranker.load(data)

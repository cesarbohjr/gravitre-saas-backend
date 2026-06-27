from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.ml.clustering import QueryClusterer
from app.services.company_intelligence_orchestrator import CompanyIntelligenceOrchestrator
from app.services.knowledge_intelligence_service import (
    distinct_normalized_count,
    label_cluster,
    run_query_clustering,
)

QBR_VARIANTS = [
    "Where's the QBR deck?",
    "Find quarterly business review slides",
    "Pull the customer review presentation",
    "QBR slides for last quarter",
    "Need the quarterly business review deck",
]


@pytest.mark.asyncio
async def test_clusters_similar_queries_together():
    qbr_embeddings = [[1.0 + i * 0.01, 0.0, 0.0] for i in range(8)]
    other_embeddings = [[0.0, 1.0 + i * 0.01, 0.0] for i in range(8)]
    embeddings = qbr_embeddings + other_embeddings
    queries = QBR_VARIANTS + [
        "Where's the QBR deck?",
        "Find quarterly business review slides",
        "Pull the customer review presentation",
    ] + [
        "How do I reset my password?",
        "VPN setup guide",
        "Install printer driver",
        "Change laptop password",
        "Email signature help",
        "Teams notification settings",
        "Slack channel archive",
        "WiFi guest access",
    ]
    clusterer = QueryClusterer(min_cluster_size=3, min_samples=2)
    metrics = await clusterer.train(embeddings=embeddings, normalized_queries=queries)
    members = clusterer.cluster_members()
    assert metrics.custom_metrics["n_clusters"] >= 1
    qbr_cluster = next(
        (member_queries for member_queries in members.values() if any("qbr" in q.lower() for q in member_queries)),
        None,
    )
    assert qbr_cluster is not None
    assert len(qbr_cluster) >= 3
    assert all("qbr" in q.lower() or "quarterly" in q.lower() or "review" in q.lower() for q in qbr_cluster)


@pytest.mark.asyncio
async def test_gated_by_minimum_row_count():
    orchestrator = CompanyIntelligenceOrchestrator()
    queries = [{"normalized_query_text": f"query {i}", "query_text": f"query {i}"} for i in range(10)]
    assert distinct_normalized_count(queries) < orchestrator.MIN_CLUSTERING_ROWS
    assert orchestrator.MIN_CLUSTERING_ROWS == 40


@pytest.mark.asyncio
async def test_run_query_clustering_skips_too_few_unique():
    queries = [
        {"normalized_query_text": "only one", "query_text": "only one"},
        {"normalized_query_text": "only one", "query_text": "only one"},
    ]
    result = await run_query_clustering(MagicMock(), "org-1", queries, client=MagicMock())
    assert result == []


@pytest.mark.asyncio
async def test_cluster_labeling_produces_readable_text():
    router = MagicMock()
    router.complete = AsyncMock(return_value=MagicMock(content="Quarterly Business Review materials"))
    label = await label_cluster(QBR_VARIANTS, org_id="org-1", router=router)
    assert "Quarterly Business Review" in label
    router.complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_assign_clusters_nearest_centroid():
    clusterer = QueryClusterer(min_cluster_size=2, min_samples=1)
    train_vectors = np.array([[1.0, 0.0], [1.01, 0.0], [0.0, 1.0], [0.0, 1.01]])
    await clusterer.train(
        embeddings=train_vectors.tolist(),
        normalized_queries=["a", "b", "c", "d"],
    )
    assigned = await clusterer.assign_clusters([[1.02, 0.0]], ["new qbr query"])
    assert assigned[0]["cluster_id"] >= 0

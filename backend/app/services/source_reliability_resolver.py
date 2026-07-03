"""Resolve live source reliability scores for intelligence surfaces."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.ml.source_reliability import compute_source_reliability, fetch_source_reliability_scores
from app.workflows.repository import get_supabase_client

GRAPH_SOURCE_DEFAULT = 0.75
RAG_SOURCE_DEFAULT = 0.55
PREDICTION_SOURCE_DEFAULT = 0.5


def _extract_document_id(source: dict[str, Any]) -> str | None:
    for key in ("document_id", "source_document_id", "documentId", "sourceDocumentId"):
        value = source.get(key)
        if value:
            return str(value)
    nested = source.get("context")
    if isinstance(nested, dict):
        for key in ("document_id", "source_document_id"):
            value = nested.get(key)
            if value:
                return str(value)
    return None


async def resolve_average_source_reliability(
    org_id: str,
    sources: list[dict[str, Any]] | None,
    settings: Settings | None = None,
) -> float | None:
    """Average empirical reliability for RAG sources; typed defaults for non-RAG."""
    if not sources:
        return None
    active = settings or get_settings()
    try:
        client = get_supabase_client(active)
        reliability_scores = await fetch_source_reliability_scores(org_id, client)
    except Exception:  # noqa: BLE001
        reliability_scores = {}
    values: list[float] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_type = str(source.get("type") or "").lower()
        if source_type in {"knowledge_graph", "graph"}:
            values.append(GRAPH_SOURCE_DEFAULT)
            continue
        if source_type == "prediction":
            values.append(PREDICTION_SOURCE_DEFAULT)
            continue
        doc_id = _extract_document_id(source)
        if doc_id and doc_id in reliability_scores:
            values.append(float(reliability_scores[doc_id]))
        elif doc_id or source.get("content") or source.get("score") is not None:
            values.append(RAG_SOURCE_DEFAULT)
    if not values:
        return None
    return round(sum(values) / len(values), 4)


async def resolve_source_credibility(
    org_id: str,
    source_ref: str,
    source_type: str,
    settings: Settings | None = None,
) -> float:
    """Org-scoped credibility for research and trust surfaces."""
    source_type = source_type.lower()
    try:
        if source_type in {"rag", "org_knowledge", "knowledge_graph", "graph"}:
            if source_type in {"knowledge_graph", "graph"}:
                return GRAPH_SOURCE_DEFAULT
            active = settings or get_settings()
            client = get_supabase_client(active)
            scores = await fetch_source_reliability_scores(org_id, client)
            if source_ref in scores:
                return round(float(scores[source_ref]), 4)
            return RAG_SOURCE_DEFAULT
        if source_ref.startswith("http"):
            active = settings or get_settings()
            client = get_supabase_client(active)
            scores = await fetch_source_reliability_scores(org_id, client)
            if source_ref in scores:
                return round(float(scores[source_ref]), 4)
            return RAG_SOURCE_DEFAULT
    except Exception:  # noqa: BLE001
        if source_type in {"knowledge_graph", "graph"}:
            return GRAPH_SOURCE_DEFAULT
        return RAG_SOURCE_DEFAULT
    reliability = compute_source_reliability(7, 10)
    return float(reliability if reliability is not None else RAG_SOURCE_DEFAULT)

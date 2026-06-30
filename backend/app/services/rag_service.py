from __future__ import annotations

import asyncio
import time
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.logging import get_logger
from app.rag.embedding import EmbeddingDimensionMismatchError, embed_with_failover
from app.rag.ingest import chunk_document_text, replace_chunks_and_embeddings, upsert_document
from app.rag.department import resolve_department_id_for_agent
from app.rag.hybrid_rerank import (
    bm25_rank_rows,
    cross_encoder_enabled,
    hybrid_candidate_k,
    normalize_chunk_row,
    rerank_rows,
    rerank_score_threshold,
    rrf_merge,
)
from app.ml.learning_to_rank import get_weight_for_org
from app.ml.source_reliability import apply_reliability_adjustment, fetch_source_reliability_scores
from app.rag.retrieval import fetch_bm25_corpus, search_chunks
from app.services.model_router import TaskType, get_model_router
from app.services.rag_outcome_tracking import record_retrieval_outcomes
from app.services.cache_service import get_cache_service
from app.services.latency_tracking import log_pipeline_latency
from app.services.rag_cache_helpers import EMBEDDING_TTL_SECONDS, RETRIEVAL_TTL_SECONDS, retrieval_cache_parts
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_MODEL = "text-embedding-3-small"


class Document(BaseModel):
    source_id: str
    external_id: str | None = None
    title: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    environment: str = "default"


class Chunk(BaseModel):
    id: str
    content: str
    score: float
    source: str | None = None


class RAGResponse(BaseModel):
    answer: str
    chunks: list[Chunk]
    metrics: dict[str, Any]


class RAGService:
    def __init__(self):
        self.settings = get_settings()
        self.model_router = get_model_router()

    async def ingest_document(self, org_id: str, document: Document) -> list[Chunk]:
        client = get_supabase_client(self.settings)
        doc = upsert_document(
            client=client,
            org_id=org_id,
            source_id=document.source_id,
            external_id=document.external_id,
            title=document.title,
            metadata=document.metadata,
            environment_name=document.environment,
        )
        chunks = chunk_document_text(document.content, settings=self.settings)
        replace_chunks_and_embeddings(
            client=client,
            settings=self.settings,
            org_id=org_id,
            source_id=document.source_id,
            document_id=str(doc["id"]),
            chunks=chunks,
            environment_name=document.environment,
        )
        return [Chunk(id=f"{doc['id']}:{i}", content=value, score=1.0, source=document.title) for i, value in enumerate(chunks)]

    async def retrieve_hybrid_rows(
        self,
        org_id: str,
        query: str,
        scope: str = "organization",
        top_k: int = 8,
        filters: dict | None = None,
        agent_id: str | None = None,
        message_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Hybrid retrieval rows with BE-10 metadata preserved for API/workflow callers."""
        retrieval_started = time.monotonic()
        filters = dict(filters or {})
        if agent_id and not filters.get("agent_id"):
            filters["agent_id"] = agent_id
        environment = str(filters.get("environment") or "default")
        top_k = top_k or self.settings.rag_top_k or 8
        client = get_supabase_client(self.settings)
        cache = get_cache_service(self.settings)
        cache_parts = retrieval_cache_parts(org_id, query, scope, top_k, filters)
        cached_payload = cache.get_sync("retrieval", *cache_parts)
        if isinstance(cached_payload, dict) and cached_payload.get("rows") is not None:
            await cache.record_hit("retrieval")
            cached_metrics = dict(cached_payload.get("metrics") or {})
            cached_metrics["cache_hit"] = True
            if message_id:
                asyncio.create_task(
                    log_pipeline_latency(
                        self.settings,
                        org_id=org_id,
                        stage_name="retrieval",
                        duration_ms=0,
                        message_id=message_id,
                        cache_hit=True,
                        client=client,
                    )
                )
            return list(cached_payload["rows"]), cached_metrics
        await cache.record_miss("retrieval")
        department_id = filters.get("department_id")
        resolved_agent_id = filters.get("agent_id")
        if scope == "department" or scope == "agent":
            resolved_dept, resolved_agent = resolve_department_id_for_agent(
                client, org_id, str(resolved_agent_id) if resolved_agent_id else None
            )
            department_id = department_id or resolved_dept
            resolved_agent_id = resolved_agent_id or resolved_agent
        elif resolved_agent_id and not department_id:
            department_id, resolved_agent_id = resolve_department_id_for_agent(
                client, org_id, str(resolved_agent_id)
            )
        embedding_method = "none"
        embedding_model = str(getattr(self.settings, "embedding_model", None) or EMBEDDING_MODEL)
        cached_embedding = cache.get_sync("embedding", embedding_model, org_id, query)
        try:
            if isinstance(cached_embedding, dict) and cached_embedding.get("vector"):
                query_embedding = cached_embedding["vector"]
                embedding_method = str(cached_embedding.get("method") or "openai")
                await cache.record_hit("embedding")
            else:
                await cache.record_miss("embedding")
                query_embedding, embedding_method = embed_with_failover(query, self.settings, org_id=org_id)
                cache.set_sync(
                    "embedding",
                    {"vector": query_embedding, "method": embedding_method},
                    EMBEDDING_TTL_SECONDS,
                    embedding_model,
                    org_id,
                    query,
                )
            logger.info("rag embedding org_id=%s method=%s", org_id, embedding_method)
        except EmbeddingDimensionMismatchError as exc:
            logger.warning("rag dimension mismatch org_id=%s error=%s", org_id, str(exc))
            keyword_rows = self._keyword_search(org_id, query, top_k=top_k, environment=environment)
            rows = [normalize_chunk_row(row) for row in keyword_rows[:top_k]]
            return rows, {
                "top_k": top_k,
                "semantic_candidates": 0,
                "keyword_candidates": len(keyword_rows),
                "reranked": len(rows),
                "embedding_method": "keyword_fallback_dimension_mismatch",
                "fallback": "voyage_dimension_mismatch",
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("rag embedding unavailable org_id=%s error=%s", org_id, str(exc))
            return [], {
                "top_k": top_k,
                "semantic_candidates": 0,
                "keyword_candidates": 0,
                "reranked": 0,
                "embedding_method": "keyword_fallback",
                "fallback": "embedding_unavailable",
            }

        candidate_k = hybrid_candidate_k(self.settings)
        merge_k = candidate_k * 2
        semantic_rows = search_chunks(
            settings=self.settings,
            org_id=org_id,
            query_embedding=query_embedding,
            top_k=candidate_k,
            source_id=(filters or {}).get("source_id"),
            document_id=(filters or {}).get("document_id"),
            environment_name=environment,
            department_id=str(department_id) if department_id else None,
            agent_id=str(resolved_agent_id) if resolved_agent_id else None,
        )
        semantic_rows = [normalize_chunk_row(row) for row in semantic_rows]

        bm25_corpus = fetch_bm25_corpus(
            self.settings,
            org_id,
            environment_name=environment,
            source_id=(filters or {}).get("source_id"),
            document_id=(filters or {}).get("document_id"),
            department_id=str(department_id) if department_id else None,
            agent_id=str(resolved_agent_id) if resolved_agent_id else None,
        )
        keyword_rows = bm25_rank_rows(query, bm25_corpus, top_k=candidate_k)
        merged = rrf_merge(semantic_rows, keyword_rows, top_k=merge_k)
        retrieval_ms = int((time.monotonic() - retrieval_started) * 1000)
        disable_rerank = bool((filters or {}).get("disable_rerank"))
        rerank_started = time.monotonic()
        if disable_rerank:
            reranked = merged[:top_k]
            rerank_method = "disabled"
        else:
            reranked, rerank_method = rerank_rows(
                query,
                merged,
                top_k=top_k,
                settings=self.settings,
            )
        rerank_ms = int((time.monotonic() - rerank_started) * 1000)
        reliability_scores = await fetch_source_reliability_scores(org_id, client)
        learned_weight = await get_weight_for_org(org_id, self.settings, client)
        reranked = apply_reliability_adjustment(reranked, reliability_scores, learned_weight)
        retrieval_latency_ms = int((time.monotonic() - retrieval_started) * 1000)
        if message_id:
            asyncio.create_task(
                log_pipeline_latency(
                    self.settings,
                    org_id=org_id,
                    stage_name="retrieval",
                    duration_ms=retrieval_ms,
                    message_id=message_id,
                    client=client,
                )
            )
            asyncio.create_task(
                log_pipeline_latency(
                    self.settings,
                    org_id=org_id,
                    stage_name="rerank",
                    duration_ms=rerank_ms,
                    message_id=message_id,
                    client=client,
                )
            )
        if message_id and reranked:
            asyncio.create_task(
                record_retrieval_outcomes(
                    self.settings,
                    org_id=org_id,
                    message_id=message_id,
                    rows=reranked,
                    retrieval_latency_ms=retrieval_latency_ms,
                    client=client,
                )
            )
        logger.info(
            "rag_rerank org_id=%s method=%s candidates=%s cross_encoder_enabled=%s reliability_sources=%s",
            org_id,
            rerank_method,
            len(merged),
            cross_encoder_enabled(self.settings),
            len(reliability_scores),
        )
        metrics = {
            "top_k": top_k,
            "semantic_candidates": len(semantic_rows),
            "keyword_candidates": len(keyword_rows),
            "reranked": len(reranked),
            "embedding_method": embedding_method,
            "hybrid_candidate_k": candidate_k,
            "rerank_method": rerank_method,
            "cross_encoder_enabled": cross_encoder_enabled(self.settings),
            "rerank_threshold": rerank_score_threshold(self.settings),
            "reliability_sources_scored": len(reliability_scores),
            "reliability_weight": learned_weight,
            "retrieval_latency_ms": retrieval_latency_ms,
        }
        cache.set_sync(
            "retrieval",
            {"rows": reranked, "metrics": metrics},
            RETRIEVAL_TTL_SECONDS,
            *cache_parts,
        )
        return reranked, metrics

    async def retrieve_chunks(
        self,
        org_id: str,
        query: str,
        scope: str = "organization",
        top_k: int = 8,
        filters: dict | None = None,
        include_sources: bool = True,
        agent_id: str | None = None,
        message_id: str | None = None,
    ) -> tuple[list[Chunk], dict[str, Any]]:
        """Hybrid retrieval without LLM answer synthesis (for agent/orchestrator context)."""
        rows, metrics = await self.retrieve_hybrid_rows(
            org_id,
            query,
            scope=scope,
            top_k=top_k,
            filters=filters,
            agent_id=agent_id,
            message_id=message_id,
        )
        chunks = [
            Chunk(
                id=str(row.get("id") or row.get("chunk_id") or ""),
                content=str(row.get("content") or ""),
                score=float(row.get("score") or 0.0),
                source=str(row.get("title") or row.get("source_title") or "")
                if include_sources
                else None,
            )
            for row in rows
        ]
        return chunks, metrics

    async def query(
        self,
        org_id: str,
        query: str,
        scope: str = "organization",
        top_k: int = 8,
        filters: dict | None = None,
        include_sources: bool = True,
        agent_id: str | None = None,
        message_id: str | None = None,
    ) -> RAGResponse:
        chunks, metrics = await self.retrieve_chunks(
            org_id,
            query,
            scope=scope,
            top_k=top_k,
            filters=filters,
            include_sources=include_sources,
            agent_id=agent_id,
            message_id=message_id,
        )
        if metrics.get("fallback") == "voyage_dimension_mismatch":
            return RAGResponse(
                answer="Semantic search degraded to keyword matching due to embedding dimension mismatch.",
                chunks=chunks,
                metrics=metrics,
            )
        if metrics.get("fallback") == "embedding_unavailable":
            return RAGResponse(
                answer="RAG is temporarily unavailable because embeddings are not configured.",
                chunks=chunks,
                metrics=metrics,
            )

        context_snippets = [snippet.content.strip() for snippet in chunks if snippet.content.strip()]
        context_snippets = [snippet for snippet in context_snippets if snippet]
        if context_snippets:
            context_block = "\n\n".join(
                f"[{idx}] {snippet}" for idx, snippet in enumerate(context_snippets, start=1)
            )
        else:
            context_block = "(no context retrieved)"
        prompt = (
            "Answer the question using ONLY the provided context. "
            "If the context is insufficient, say so explicitly.\n\n"
            f"Question:\n{query}\n\n"
            f"Context:\n{context_block}"
        )
        try:
            answer_resp = await self.model_router.complete(
                task_type=TaskType.RAG_ANSWERING,
                prompt=prompt,
                system_prompt=(
                    "Answer only from the provided context and cite factual points "
                    "from it. Never fabricate sources or facts. If the context is "
                    "empty or insufficient to answer, say so explicitly and do not "
                    "guess."
                ),
                org_id=org_id,
            )
            answer_text = answer_resp.content
        except Exception as exc:  # noqa: BLE001
            logger.warning("rag answer fallback org_id=%s error=%s", org_id, str(exc))
            answer_text = "I could not generate a model answer right now. Retrieved context is returned for review."
        return RAGResponse(answer=answer_text, chunks=chunks, metrics=metrics)

    def _keyword_search(self, org_id: str, query: str, top_k: int, environment: str) -> list[dict[str, Any]]:
        """Legacy ilike keyword fallback when embeddings are unavailable."""
        client = get_supabase_client(self.settings)
        terms = [t for t in query.split() if len(t) > 2][:5]
        if not terms:
            return []
        or_filters = ",".join(f"content.ilike.%{term}%" for term in terms)
        resp = (
            client.table("rag_chunks")
            .select("id,content,document_id,chunk_index,created_at")
            .eq("org_id", org_id)
            .eq("environment", environment)
            .or_(or_filters)
            .limit(top_k)
            .execute()
        )
        doc_ids = sorted({str(row.get("document_id")) for row in (resp.data or []) if row.get("document_id")})
        title_map: dict[str, str] = {}
        if doc_ids:
            doc_resp = (
                client.table("rag_documents")
                .select("id,title")
                .eq("org_id", org_id)
                .in_("id", doc_ids)
                .limit(len(doc_ids))
                .execute()
            )
            title_map = {str(doc["id"]): str(doc.get("title") or "") for doc in (doc_resp.data or [])}
        rows = []
        for row in resp.data or []:
            document_id = row.get("document_id")
            rows.append(
                {
                    "id": row.get("id"),
                    "chunk_id": row.get("id"),
                    "content": row.get("content"),
                    "score": 0.4,
                    "title": title_map.get(str(document_id), ""),
                    "document_id": document_id,
                    "document_title": title_map.get(str(document_id), ""),
                    "chunk_index": row.get("chunk_index") or 0,
                }
            )
        return rows

    def _rrf_merge(self, semantic_rows: list[dict], keyword_rows: list[dict], top_k: int) -> list[dict]:
        return rrf_merge(semantic_rows, keyword_rows, top_k=top_k)

    def _rerank(self, query: str, rows: list[dict], top_k: int) -> list[dict]:
        reranked, _method = rerank_rows(query, rows, top_k=top_k, settings=self.settings)
        return reranked


_rag_service_singleton: RAGService | None = None


def get_rag_service() -> RAGService:
    global _rag_service_singleton
    if _rag_service_singleton is None:
        _rag_service_singleton = RAGService()
    return _rag_service_singleton

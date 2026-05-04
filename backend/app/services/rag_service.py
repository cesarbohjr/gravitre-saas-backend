from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.logging import get_logger
from app.rag.embedding import get_embedding
from app.rag.ingest import chunk_text, replace_chunks_and_embeddings, upsert_document
from app.rag.retrieval import search_chunks
from app.services.model_router import TaskType, get_model_router
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
        chunks = chunk_text(
            document.content,
            min_chars=self.settings.rag_chunk_overlap or CHUNK_OVERLAP,
            max_chars=self.settings.rag_chunk_size or CHUNK_SIZE,
            overlap=self.settings.rag_chunk_overlap or CHUNK_OVERLAP,
        )
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

    async def query(
        self,
        org_id: str,
        query: str,
        scope: str = "organization",
        top_k: int = 8,
        filters: dict | None = None,
        include_sources: bool = True,
    ) -> RAGResponse:
        _ = scope
        environment = str((filters or {}).get("environment") or "default")
        top_k = top_k or self.settings.rag_top_k or 8
        try:
            query_embedding = get_embedding(query, self.settings)
        except Exception as exc:  # noqa: BLE001
            logger.warning("rag embedding unavailable org_id=%s error=%s", org_id, str(exc))
            return RAGResponse(
                answer="RAG is temporarily unavailable because embeddings are not configured.",
                chunks=[],
                metrics={
                    "top_k": top_k,
                    "semantic_candidates": 0,
                    "keyword_candidates": 0,
                    "reranked": 0,
                    "fallback": "embedding_unavailable",
                },
            )
        semantic_rows = search_chunks(
            settings=self.settings,
            org_id=org_id,
            query_embedding=query_embedding,
            top_k=max(top_k * 2, top_k),
            source_id=(filters or {}).get("source_id"),
            document_id=(filters or {}).get("document_id"),
            environment_name=environment,
        )

        keyword_rows = self._keyword_search(org_id, query, top_k=max(top_k * 2, top_k), environment=environment)
        merged = self._rrf_merge(semantic_rows, keyword_rows, top_k=top_k)
        reranked = self._rerank(query, merged, top_k=top_k)

        context_snippets = [row.get("content") or "" for row in reranked]
        prompt = (
            "Answer using the provided context. If context is insufficient, say so.\n"
            f"Question: {query}\n"
            f"Context: {context_snippets}"
        )
        try:
            answer_resp = await self.model_router.complete(
                task_type=TaskType.RAG_ANSWERING,
                prompt=prompt,
                system_prompt="Cite factual points from context. Do not fabricate sources.",
                org_id=org_id,
            )
            answer_text = answer_resp.content
        except Exception as exc:  # noqa: BLE001
            logger.warning("rag answer fallback org_id=%s error=%s", org_id, str(exc))
            answer_text = "I could not generate a model answer right now. Retrieved context is returned for review."
        chunks = [
            Chunk(
                id=str(row.get("id")),
                content=str(row.get("content") or ""),
                score=float(row.get("score") or 0.0),
                source=str(row.get("title") or "") if include_sources else None,
            )
            for row in reranked
        ]
        return RAGResponse(
            answer=answer_text,
            chunks=chunks,
            metrics={
                "top_k": top_k,
                "semantic_candidates": len(semantic_rows),
                "keyword_candidates": len(keyword_rows),
                "reranked": len(reranked),
            },
        )

    def _keyword_search(self, org_id: str, query: str, top_k: int, environment: str) -> list[dict[str, Any]]:
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
            rows.append(
                {
                    "id": row.get("id"),
                    "content": row.get("content"),
                    "score": 0.4,
                    "title": title_map.get(str(row.get("document_id")), ""),
                }
            )
        return rows

    def _rrf_merge(self, semantic_rows: list[dict], keyword_rows: list[dict], top_k: int) -> list[dict]:
        k = 50.0
        scores: dict[str, dict[str, Any]] = {}
        for rank, row in enumerate(semantic_rows, start=1):
            row_id = str(row.get("id"))
            if row_id not in scores:
                scores[row_id] = dict(row)
                scores[row_id]["score"] = 0.0
            scores[row_id]["score"] += 1 / (k + rank)
        for rank, row in enumerate(keyword_rows, start=1):
            row_id = str(row.get("id"))
            if row_id not in scores:
                scores[row_id] = dict(row)
                scores[row_id]["score"] = 0.0
            scores[row_id]["score"] += 1 / (k + rank)
        merged = list(scores.values())
        merged.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
        return merged[:top_k]

    def _rerank(self, query: str, rows: list[dict], top_k: int) -> list[dict]:
        q_terms = set(query.lower().split())
        for row in rows:
            content = str(row.get("content") or "").lower()
            overlap = len([t for t in q_terms if t in content])
            row["score"] = float(row.get("score") or 0.0) + overlap * 0.05
        rows.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
        return rows[:top_k]


_rag_service_singleton: RAGService | None = None


def get_rag_service() -> RAGService:
    global _rag_service_singleton
    if _rag_service_singleton is None:
        _rag_service_singleton = RAGService()
    return _rag_service_singleton

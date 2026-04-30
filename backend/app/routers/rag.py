"""BE-10: Read-only RAG — POST /api/rag/retrieve. Auth required; org from context."""
import time
import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.billing.service import (
    apply_usage_with_overage,
    build_ai_usage_metadata,
    get_current_period,
    get_default_usage_quantity,
    get_plan_for_org,
    record_usage,
)
from app.config import Settings, get_settings
from app.core.logging import get_logger, request_id_ctx
from app.rag.embedding import get_embedding
from app.rag.retrieval import search_chunks

logger = get_logger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])

TOP_K_DEFAULT = 10
TOP_K_MAX = 50


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=TOP_K_DEFAULT, ge=1, le=TOP_K_MAX)
    source_id: UUID | None = None
    document_id: UUID | None = None
    min_score: float | None = Field(default=None, ge=0, le=1)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, alias="topK")
    min_score: float | None = Field(default=None, alias="minScore", ge=0, le=1)


class ChunkOut(BaseModel):
    id: str
    text: str
    source_id: str
    source_title: str
    document_id: str
    document_title: str | None
    chunk_index: int
    score: float


class RetrieveResponse(BaseModel):
    query_id: str
    chunks: list[ChunkOut]
    total: int


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(
    body: RetrieveRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RetrieveResponse:
    """Vector search over org RAG chunks. Org from auth; no org_id in body."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required for retrieval",
        )

    query_id = str(uuid.uuid4())
    start = time.perf_counter()

    try:
        embedding = get_embedding(body.query, settings)
    except Exception as e:
        logger.warning("rag_embedding_failure request_id=%s", request_id_ctx.get(), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Retrieval temporarily unavailable",
        ) from e

    try:
        rows = search_chunks(
            settings=settings,
            org_id=org_id,
            query_embedding=embedding,
            top_k=body.top_k,
            source_id=str(body.source_id) if body.source_id else None,
            document_id=str(body.document_id) if body.document_id else None,
            environment_name=environment_name,
        )
    except Exception as e:
        logger.warning("rag_search_failure request_id=%s", request_id_ctx.get(), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Retrieval temporarily unavailable",
        ) from e

    if body.min_score is not None:
        rows = [r for r in rows if (r.get("score") or 0) >= body.min_score]

    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        plan = get_plan_for_org(client, org_id)
        period_start, period_end = get_current_period()
        ai_meta = build_ai_usage_metadata(
            input_texts=[body.query],
            output_texts=[],
            model_name=settings.embedding_model,
            source="rag.query",
            source_id=query_id,
        )
        apply_usage_with_overage(
            client=client,
            org_id=org_id,
            environment=environment_name,
            metric_type="ai_credits",
            quantity=int(ai_meta["credits"]),
            plan=plan,
            period_start=period_start,
            period_end=period_end,
            metadata=ai_meta,
        )
        record_usage(
            client=client,
            org_id=org_id,
            environment=environment_name,
            metric_type="rag_usage",
            quantity=get_default_usage_quantity("rag_usage"),
            period_start=period_start,
            period_end=period_end,
        )
    except Exception:
        pass

    chunks_out = [
        ChunkOut(
            id=str(row["chunk_id"]),
            text=row["content"],
            source_id=str(row["source_id"]),
            source_title=row["source_title"] or "",
            document_id=str(row["document_id"]),
            document_title=row.get("document_title"),
            chunk_index=row["chunk_index"],
            score=round(float(row["score"]), 6),
        )
        for row in rows
    ]

    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "rag_retrieve request_id=%s org_id=%s latency_ms=%s result_count=%s query_id=%s",
        request_id_ctx.get(),
        org_id,
        latency_ms,
        len(chunks_out),
        query_id,
        extra={
            "request_id": request_id_ctx.get(),
            "org_id": org_id,
            "latency_ms": latency_ms,
            "result_count": len(chunks_out),
            "query_id": query_id,
        },
    )

    # Optional: write to rag_retrieval_logs (no query text)
    try:
        from supabase import create_client
        client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        client.table("rag_retrieval_logs").insert({
            "org_id": org_id,
            "query_id": query_id,
            "result_count": len(chunks_out),
            "latency_ms": latency_ms,
            "environment": environment_name,
        }).execute()
    except Exception:
        pass  # non-fatal; do not fail response

    return RetrieveResponse(
        query_id=query_id,
        chunks=chunks_out,
        total=len(chunks_out),
    )


@router.post("/query")
async def query_alias(
    body: QueryRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RetrieveResponse:
    """Alias for /api/rag/retrieve with spec response shape."""
    req = RetrieveRequest(
        query=body.query,
        top_k=body.top_k or TOP_K_DEFAULT,
        min_score=body.min_score,
    )
    res = await retrieve(req, _user, org_id, environment_name, settings)
    return {
        "results": [
            {
                "score": chunk.score,
                "sourceId": chunk.source_id,
                "documentId": chunk.document_id,
                "chunkText": chunk.text,
                "chunkIndex": chunk.chunk_index,
                "metadata": {},
            }
            for chunk in res.chunks
        ]
    }

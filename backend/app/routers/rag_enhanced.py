from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.services.rag_service import Document, RAGResponse, RAGService, get_rag_service

router = APIRouter(prefix="/api/rag-enhanced", tags=["rag-enhanced"])


class RAGIngestRequest(BaseModel):
    source_id: str
    external_id: str | None = None
    title: str | None = None
    content: str = Field(..., min_length=1)
    metadata: dict = Field(default_factory=dict)
    environment: str = "production"


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    scope: str = "organization"
    top_k: int = Field(default=8, ge=1, le=50)
    filters: dict | None = None
    include_sources: bool = True


@router.post("/ingest")
async def ingest_document(
    body: RAGIngestRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    rag_service: RAGService = Depends(get_rag_service),
) -> dict:
    _user, org_id = _admin
    chunks = await rag_service.ingest_document(
        org_id=org_id,
        document=Document(
            source_id=body.source_id,
            external_id=body.external_id,
            title=body.title,
            content=body.content,
            metadata=body.metadata,
            environment=body.environment,
        ),
    )
    return {"chunks": [chunk.model_dump() for chunk in chunks], "total": len(chunks)}


@router.post("/query", response_model=RAGResponse)
async def query_rag(
    body: RAGQueryRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    rag_service: RAGService = Depends(get_rag_service),
) -> RAGResponse:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    return await rag_service.query(
        org_id=org_id,
        query=body.query,
        scope=body.scope,
        top_k=body.top_k,
        filters=body.filters,
        include_sources=body.include_sources,
    )

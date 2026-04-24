"""DC-00: Admin-controlled RAG sources and ingestion. Org-scoped."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.config import Settings, get_settings
from app.rag.ingest import (
    create_ingest_job,
    create_source,
    get_document,
    get_document_chunks,
    get_ingest_job,
    get_source,
    list_documents,
    list_sources,
    update_source,
    validate_chunks,
    validate_payload_size,
)
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/rag", tags=["rag-admin"])

RESOURCE_TYPE_RAG_SOURCE = "rag_source"
RESOURCE_TYPE_RAG_INGEST = "rag_ingest"
ALLOWED_SOURCE_TYPES = {"manual", "internal", "external", "product", "support"}


class SourceCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    metadata: dict | None = None


class SourceUpdateRequest(BaseModel):
    title: str | None = None
    metadata: dict | None = None


class IngestRequest(BaseModel):
    source_id: UUID
    external_id: str | None = None
    title: str | None = None
    metadata: dict | None = None
    chunks: list[str] | None = None
    text: str | None = None
    chunking: dict | None = None


@router.get("/sources")
async def list_sources_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return {"sources": list_sources(client, org_id, environment_name=environment_name)}


@router.post("/sources", status_code=status.HTTP_201_CREATED)
async def create_source_route(
    body: SourceCreateRequest,
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin_ctx
    if body.type not in ALLOWED_SOURCE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid source type")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    source = create_source(
        client,
        org_id,
        body.title,
        body.type,
        body.metadata,
        user["user_id"],
        environment_name=environment_name,
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action="rag.source.created",
        resource_type=RESOURCE_TYPE_RAG_SOURCE,
        resource_id=source["id"],
        metadata={"type": body.type},
    )
    return {"id": str(source["id"]), "title": source["title"], "type": source["type"], "metadata": source.get("metadata")}


@router.patch("/sources/{source_id}")
async def update_source_route(
    source_id: UUID,
    body: SourceUpdateRequest,
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin_ctx
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    payload = {}
    if body.title is not None:
        payload["title"] = body.title
    if body.metadata is not None:
        payload["metadata"] = body.metadata
    source = update_source(client, org_id, str(source_id), payload, environment_name=environment_name)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action="rag.source.updated",
        resource_type=RESOURCE_TYPE_RAG_SOURCE,
        resource_id=source["id"],
        metadata={"fields": list(payload.keys())},
    )
    return {"id": str(source["id"]), "title": source["title"], "type": source["type"], "metadata": source.get("metadata")}


@router.get("/sources/{source_id}")
async def get_source_route(
    source_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    source = get_source(client, org_id, str(source_id), environment_name=environment_name)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return source


@router.get("/documents")
async def list_documents_route(
    source_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return {"documents": list_documents(client, org_id, str(source_id), environment_name=environment_name)}


@router.get("/documents/{doc_id}")
async def get_document_route(
    doc_id: UUID,
    *,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    include_chunks: bool = Query(default=False),
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    if include_chunks:
        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        r = (
            client.table("organization_members")
            .select("role")
            .eq("org_id", org_id)
            .eq("user_id", user["user_id"])
            .limit(1)
            .execute()
        )
        if not r.data or r.data[0].get("role") != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required for include_chunks")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    doc = get_document(client, org_id, str(doc_id), environment_name=environment_name)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if include_chunks:
        chunks = get_document_chunks(client, org_id, str(doc_id), limit=100, environment_name=environment_name)
        doc["chunks"] = chunks
    return doc


@router.post("/ingest")
async def ingest_route(
    body: IngestRequest,
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin_ctx
    if settings.disable_ingestion:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Ingestion is disabled")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    source = get_source(client, org_id, str(body.source_id), environment_name=environment_name)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    if (body.chunks is None and body.text is None) or (body.chunks is not None and body.text is not None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide either chunks or text, not both")
    if body.chunks is not None:
        validate_chunks(body.chunks)
    else:
        validate_payload_size(body.text or "")

    request_payload = {
        "source_id": str(body.source_id),
        "external_id": body.external_id,
        "title": body.title,
        "metadata": body.metadata,
        "chunks": body.chunks,
        "text": body.text,
        "chunking": body.chunking,
    }
    job = create_ingest_job(
        client,
        org_id,
        str(body.source_id),
        body.external_id,
        user["user_id"],
        request_payload=request_payload,
        environment_name=environment_name,
    )
    job_id = str(job["id"])

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action="rag.ingest.queued",
        resource_type=RESOURCE_TYPE_RAG_INGEST,
        resource_id=job_id,
        metadata={
            "source_id": str(body.source_id),
            "has_external_id": bool(body.external_id),
        },
    )

    return {
        "ingest_id": job_id,
        "document_id": None,
        "source_id": str(body.source_id),
        "external_id": body.external_id,
        "chunk_count": 0,
        "embedding_model": settings.openai_embedding_model,
        "embedding_dimension": settings.openai_embedding_dimension,
        "status": "queued",
    }


@router.get("/ingest/{ingest_id}")
async def get_ingest_route(
    ingest_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    job = get_ingest_job(client, org_id, str(ingest_id), environment_name=environment_name)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingest job not found")
    return {
        "id": str(job["id"]),
        "status": job["status"],
        "source_id": str(job["source_id"]),
        "document_id": str(job["document_id"]) if job.get("document_id") else None,
        "external_id": job.get("external_id"),
        "chunk_count": job.get("chunk_count", 0),
        "model": job.get("model"),
        "dimension": job.get("dimension"),
        "error_code": job.get("error_code"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
    }

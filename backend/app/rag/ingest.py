"""DC-00: Admin-controlled ingestion. No crawling; no file bytes."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from supabase import Client

from app.config import Settings
from app.rag.embedding import get_embedding

# Size limits
MAX_TEXT_BYTES = 2 * 1024 * 1024  # 2 MiB
MAX_CHUNKS = 500
MAX_CHUNK_BYTES = 16 * 1024  # 16 KiB

# Chunking defaults (approx tokens -> chars at 4 chars/token)
CHUNK_MIN_CHARS = 1024   # ~256 tokens
CHUNK_MAX_CHARS = 2048   # ~512 tokens
CHUNK_OVERLAP_CHARS = 200  # ~50 tokens


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_payload_size(text: str) -> None:
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError("Text payload exceeds maximum size")


def chunk_text(
    text: str,
    min_chars: int = CHUNK_MIN_CHARS,
    max_chars: int = CHUNK_MAX_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """Deterministic char-based chunking with overlap. No external deps."""
    text = (text or "").strip()
    if not text:
        return []
    max_chars = max(256, max_chars)
    min_chars = max(128, min(min_chars, max_chars))
    overlap = max(0, min(overlap_chars, max_chars - 1))
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
        if len(chunks) > MAX_CHUNKS:
            raise ValueError("Chunk count exceeds maximum")
    return chunks


def validate_chunks(chunks: list[str]) -> None:
    if not chunks:
        raise ValueError("Chunks array is empty")
    if len(chunks) > MAX_CHUNKS:
        raise ValueError("Chunk count exceeds maximum")
    for c in chunks:
        if not isinstance(c, str) or not c.strip():
            raise ValueError("All chunks must be non-empty strings")
        if len(c.encode("utf-8")) > MAX_CHUNK_BYTES:
            raise ValueError("Chunk exceeds maximum size")


def get_source(client: Client, org_id: str, source_id: str, environment_name: str = "default") -> dict | None:
    r = (
        client.table("rag_sources")
        .select("*")
        .eq("id", source_id)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def list_sources(client: Client, org_id: str, environment_name: str = "default") -> list[dict]:
    r = (
        client.table("rag_sources")
        .select("id, title, type, metadata, created_at, updated_at")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .order("updated_at", desc=True)
        .execute()
    )
    return list(r.data or [])


def create_source(
    client: Client,
    org_id: str,
    title: str,
    type_: str,
    metadata: dict | None,
    created_by: str,
    environment_name: str = "default",
) -> dict:
    row = {
        "org_id": org_id,
        "title": title,
        "type": type_,
        "metadata": metadata or {},
        "created_by": created_by,
        "environment": environment_name,
    }
    r = client.table("rag_sources").insert(row).execute()
    if not r.data:
        raise RuntimeError("rag_sources insert returned no row")
    return dict(r.data[0])


def update_source(
    client: Client,
    org_id: str,
    source_id: str,
    payload: dict[str, Any],
    environment_name: str = "default",
) -> dict | None:
    if not payload:
        return get_source(client, org_id, source_id, environment_name=environment_name)
    r = (
        client.table("rag_sources")
        .update(payload)
        .eq("id", source_id)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def list_documents(
    client: Client,
    org_id: str,
    source_id: str,
    environment_name: str = "default",
) -> list[dict]:
    r = (
        client.table("rag_documents")
        .select("id, title, external_id, metadata, updated_at")
        .eq("org_id", org_id)
        .eq("source_id", source_id)
        .eq("is_active", True)
        .eq("environment", environment_name)
        .order("updated_at", desc=True)
        .execute()
    )
    return list(r.data or [])


def get_document(
    client: Client,
    org_id: str,
    doc_id: str,
    environment_name: str = "default",
) -> dict | None:
    r = (
        client.table("rag_documents")
        .select("id, title, external_id, metadata, updated_at, source_id")
        .eq("org_id", org_id)
        .eq("id", doc_id)
        .eq("environment", environment_name)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def get_document_chunks(
    client: Client,
    org_id: str,
    doc_id: str,
    limit: int = 100,
    environment_name: str = "default",
) -> list[dict]:
    r = (
        client.table("rag_chunks")
        .select("id, chunk_index, content, created_at")
        .eq("org_id", org_id)
        .eq("document_id", doc_id)
        .eq("environment", environment_name)
        .order("chunk_index")
        .limit(limit)
        .execute()
    )
    return list(r.data or [])


def upsert_document(
    client: Client,
    org_id: str,
    source_id: str,
    external_id: str | None,
    title: str | None,
    metadata: dict | None,
    is_active: bool | None = None,
    environment_name: str = "default",
) -> dict:
    row = {
        "org_id": org_id,
        "source_id": source_id,
        "external_id": external_id,
        "title": title,
        "metadata": metadata or {},
        "environment": environment_name,
    }
    if is_active is not None:
        row["is_active"] = is_active
    elif external_id:
        # Create new inactive version; activate after full ingest
        row["is_active"] = False
    else:
        row["is_active"] = True
    r = client.table("rag_documents").insert(row).execute()
    if not r.data:
        raise RuntimeError("rag_documents insert returned no row")
    return dict(r.data[0])


def replace_chunks_and_embeddings(
    client: Client,
    settings: Settings,
    org_id: str,
    source_id: str,
    document_id: str,
    chunks: list[str],
    environment_name: str = "default",
    heartbeat_cb: Callable[[], None] | None = None,
) -> int:
    """Replace chunks for a document and insert embeddings. Returns chunk_count."""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY required for embeddings")
    rows = []
    for i, content in enumerate(chunks):
        rows.append({
            "org_id": org_id,
            "document_id": document_id,
            "source_id": source_id,
            "content": content,
            "chunk_index": i,
            "environment": environment_name,
        })
    if not rows:
        return 0
    r = client.table("rag_chunks").insert(rows).execute()
    if not r.data:
        raise RuntimeError("rag_chunks insert returned no rows")
    chunk_ids = [c["id"] for c in r.data]
    if heartbeat_cb:
        heartbeat_cb()
    for idx, (chunk_id, content) in enumerate(zip(chunk_ids, chunks)):
        embedding = get_embedding(content, settings)
        client.table("rag_embeddings").insert({
            "chunk_id": chunk_id,
            "org_id": org_id,
            "embedding": embedding,
            "model_version": settings.embedding_model,
            "environment": environment_name,
        }).execute()
        if heartbeat_cb and idx > 0 and (idx % 10 == 0):
            heartbeat_cb()
    return len(chunks)


def activate_document_version(
    client: Client,
    org_id: str,
    source_id: str,
    external_id: str,
    new_doc_id: str,
) -> None:
    """Atomically activate new version and archive previous versions."""
    client.rpc(
        "activate_rag_document_version",
        {
            "p_org_id": org_id,
            "p_new_doc_id": new_doc_id,
            "p_source_id": source_id,
            "p_external_id": external_id,
        },
    ).execute()


def activate_document(client: Client, org_id: str, doc_id: str) -> None:
    """Activate a document that was ingested in the background."""
    client.table("rag_documents").update({
        "is_active": True,
        "archived_at": None,
    }).eq("id", doc_id).eq("org_id", org_id).execute()


def cleanup_document_version(client: Client, org_id: str, doc_id: str) -> None:
    """Remove a failed staged document and its chunks (CASCADE)."""
    client.table("rag_documents").delete().eq("id", doc_id).eq("org_id", org_id).execute()


def create_ingest_job(
    client: Client,
    org_id: str,
    source_id: str,
    external_id: str | None,
    created_by: str,
    request_payload: dict | None = None,
    environment_name: str = "default",
) -> dict:
    row = {
        "org_id": org_id,
        "source_id": source_id,
        "external_id": external_id,
        "status": "queued",
        "created_by": created_by,
        "request_payload": request_payload or {},
        "environment": environment_name,
    }
    r = client.table("rag_ingest_jobs").insert(row).execute()
    if not r.data:
        raise RuntimeError("rag_ingest_jobs insert returned no row")
    return dict(r.data[0])


def finalize_ingest_job(
    client: Client,
    job_id: str,
    status: str,
    document_id: str | None,
    chunk_count: int,
    model: str,
    dimension: int,
    error_code: str | None = None,
    clear_payload: bool = False,
) -> None:
    payload = {
        "status": status,
        "document_id": document_id,
        "chunk_count": chunk_count,
        "model": model,
        "dimension": dimension,
        "error_code": error_code,
        "completed_at": _now_iso(),
        "worker_id": None,
        "heartbeat_at": None,
    }
    if clear_payload:
        payload["request_payload"] = None
    payload["updated_at"] = _now_iso()
    client.table("rag_ingest_jobs").update(payload).eq("id", job_id).execute()


def get_ingest_job(
    client: Client,
    org_id: str,
    job_id: str,
    environment_name: str = "default",
) -> dict | None:
    r = (
        client.table("rag_ingest_jobs")
        .select("*")
        .eq("org_id", org_id)
        .eq("id", job_id)
        .eq("environment", environment_name)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])

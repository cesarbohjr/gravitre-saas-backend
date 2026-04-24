"""Phase 6: background ingestion worker (poll/claim loop)."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from supabase import Client, create_client

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.rag.ingest import (
    activate_document,
    chunk_text,
    cleanup_document_version,
    finalize_ingest_job,
    replace_chunks_and_embeddings,
    upsert_document,
    validate_chunks,
    validate_payload_size,
)
from app.workflows.audit import write_audit_event

logger = get_logger(__name__)


def _claim_job(client: Client, worker_id: str, visibility_timeout_s: int = 300) -> dict | None:
    r = client.rpc(
        "claim_rag_ingest_job",
        {
            "p_worker_id": worker_id,
            "p_visibility_timeout_seconds": visibility_timeout_s,
        },
    ).execute()
    rows = r.data or []
    if isinstance(rows, dict):
        return rows
    if rows:
        return rows[0]
    return None


def _parse_payload(job: dict) -> dict[str, Any]:
    payload = job.get("request_payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    return payload if isinstance(payload, dict) else {}


def _heartbeat_job(client: Client, job_id: str, worker_id: str) -> None:
    if not worker_id:
        return
    try:
        client.rpc(
            "heartbeat_rag_ingest_job",
            {"p_job_id": job_id, "p_worker_id": worker_id},
        ).execute()
    except Exception:
        logger.warning("rag_ingest_heartbeat_failed job_id=%s worker_id=%s", job_id, worker_id)


def process_job(settings: Settings, client: Client, job: dict) -> None:
    org_id = str(job["org_id"])
    job_id = str(job["id"])
    worker_id = (job.get("worker_id") or "").strip()
    environment = (job.get("environment") or "default").strip() or "default"
    payload = _parse_payload(job)
    source_id = str(job["source_id"])
    external_id = job.get("external_id") or payload.get("external_id")
    title = payload.get("title")
    metadata = payload.get("metadata")
    chunks = payload.get("chunks")
    text = payload.get("text")
    chunking = payload.get("chunking") or {}

    try:
        if job.get("created_by"):
            write_audit_event(
                client,
                org_id=org_id,
                actor_id=str(job["created_by"]),
                action="rag.ingest.started",
                resource_type="rag_ingest",
                resource_id=str(job["id"]),
                metadata={
                    "source_id": source_id,
                    "has_external_id": bool(external_id),
                },
            )
        _heartbeat_job(client, job_id, worker_id)
        if (chunks is None and text is None) or (chunks is not None and text is not None):
            raise ValueError("Provide either chunks or text, not both")
        if chunks is not None:
            validate_chunks(chunks)
        else:
            validate_payload_size(text or "")
            min_chars = int(chunking.get("target_tokens_min", 256)) * 4
            max_chars = int(chunking.get("target_tokens_max", 512)) * 4
            overlap = int(chunking.get("overlap_tokens", 50)) * 4
            min_chars = max(256, min(min_chars, 4096))
            max_chars = max(min_chars, min(max_chars, 8192))
            overlap = max(0, min(overlap, max_chars - 1))
            chunks = chunk_text(text or "", min_chars, max_chars, overlap)
            validate_chunks(chunks)

        _heartbeat_job(client, job_id, worker_id)
        doc = upsert_document(
            client,
            org_id=org_id,
            source_id=source_id,
            external_id=external_id,
            title=title,
            metadata=metadata,
            is_active=False,
            environment_name=environment,
        )
        chunk_count = replace_chunks_and_embeddings(
            client,
            settings,
            org_id,
            source_id=source_id,
            document_id=str(doc["id"]),
            chunks=chunks,
            environment_name=environment,
            heartbeat_cb=lambda: _heartbeat_job(client, job_id, worker_id),
        )
        _heartbeat_job(client, job_id, worker_id)
        if external_id:
            client.rpc(
                "activate_rag_document_version",
                {
                    "p_org_id": org_id,
                    "p_new_doc_id": str(doc["id"]),
                    "p_source_id": source_id,
                    "p_external_id": external_id,
                },
            ).execute()
        else:
            activate_document(client, org_id=org_id, doc_id=str(doc["id"]))
        finalize_ingest_job(
            client,
            job_id=job_id,
            status="completed",
            document_id=str(doc["id"]),
            chunk_count=chunk_count,
            model=settings.openai_embedding_model,
            dimension=settings.openai_embedding_dimension,
            clear_payload=True,
        )
        if job.get("created_by"):
            write_audit_event(
                client,
                org_id=org_id,
                actor_id=str(job["created_by"]),
                action="rag.ingest.completed",
                resource_type="rag_ingest",
                resource_id=str(job["id"]),
                metadata={
                    "source_id": source_id,
                    "document_id": str(doc["id"]),
                    "chunk_count": chunk_count,
                    "has_external_id": bool(external_id),
                },
            )
    except ValueError as e:
        if "doc" in locals():
            cleanup_document_version(client, org_id, str(doc["id"]))
        finalize_ingest_job(
            client,
            job_id=str(job["id"]),
            status="failed",
            document_id=None,
            chunk_count=0,
            model=settings.openai_embedding_model,
            dimension=settings.openai_embedding_dimension,
            error_code="validation",
            clear_payload=True,
        )
        if job.get("created_by"):
            write_audit_event(
                client,
                org_id=org_id,
                actor_id=str(job["created_by"]),
                action="rag.ingest.failed",
                resource_type="rag_ingest",
                resource_id=str(job["id"]),
                metadata={
                    "source_id": source_id,
                    "has_external_id": bool(external_id),
                },
            )
        logger.warning("rag_ingest_failed org_id=%s job_id=%s error=validation", org_id, str(job["id"]))
    except Exception:
        if "doc" in locals():
            cleanup_document_version(client, org_id, str(doc["id"]))
        finalize_ingest_job(
            client,
            job_id=str(job["id"]),
            status="failed",
            document_id=None,
            chunk_count=0,
            model=settings.openai_embedding_model,
            dimension=settings.openai_embedding_dimension,
            error_code="ingest_failed",
            clear_payload=True,
        )
        if job.get("created_by"):
            write_audit_event(
                client,
                org_id=org_id,
                actor_id=str(job["created_by"]),
                action="rag.ingest.failed",
                resource_type="rag_ingest",
                resource_id=str(job["id"]),
                metadata={
                    "source_id": source_id,
                    "has_external_id": bool(external_id),
                },
            )
        logger.warning("rag_ingest_failed org_id=%s job_id=%s error=ingest_failed", org_id, str(job["id"]))


def run_worker(
    poll_interval_s: int = 5,
    visibility_timeout_s: int = 300,
    worker_id: str | None = None,
) -> None:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    worker_id = worker_id or f"rag-worker-{uuid.uuid4().hex[:12]}"
    logger.info(
        "rag_worker_started poll_interval_s=%s visibility_timeout_s=%s worker_id=%s",
        poll_interval_s,
        visibility_timeout_s,
        worker_id,
    )
    while True:
        if settings.disable_ingestion:
            time.sleep(poll_interval_s)
            continue
        job = _claim_job(client, worker_id=worker_id, visibility_timeout_s=visibility_timeout_s)
        if job:
            process_job(settings, client, job)
        else:
            time.sleep(poll_interval_s)


if __name__ == "__main__":
    run_worker()

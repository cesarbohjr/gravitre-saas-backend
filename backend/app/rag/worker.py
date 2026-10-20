"""Phase 6: background ingestion worker (poll/claim loop)."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from typing import Any

from supabase import Client, create_client
from app.core.db import shared_service_client

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.rag.contextual_enrichment import build_document_synopsis, enrichment_enabled
from app.rag.ingest import (
    activate_document,
    chunk_document_text,
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


def content_checksum(title: str | None, chunks: list[str]) -> str:
    h = hashlib.sha256()
    h.update((title or "").encode("utf-8"))
    for chunk in chunks:
        h.update(b"\x1e")
        h.update(chunk.encode("utf-8"))
    return h.hexdigest()


def _unchanged_active_document(
    settings: Settings,
    client: Client,
    org_id: str,
    source_id: str,
    external_id: str | None,
    content_sha256: str,
) -> str | None:
    """Id of the active version with identical content, when checksum skip is on."""
    if not external_id or getattr(settings, "rag_ingest_checksum_skip_enabled", False) is not True:
        return None
    try:
        res = (
            client.table("rag_documents")
            .select("id, metadata")
            .eq("org_id", org_id)
            .eq("source_id", source_id)
            .eq("external_id", external_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("rag_ingest_checksum_lookup_failed org_id=%s error=%s", org_id, exc)
        return None
    rows = res.data or []
    if not rows:
        return None
    meta = rows[0].get("metadata") if isinstance(rows[0].get("metadata"), dict) else {}
    if meta.get("content_sha256") == content_sha256:
        return str(rows[0]["id"])
    return None


def _discard_if_source_deleted(client: Client, org_id: str, job_id: str, doc_id: str) -> bool:
    """Drop this job's document version when deletion propagation cancelled the job.

    Deletion propagation fails queued/running jobs of records the provider deleted
    (``error_code='source_deleted'``) or archived (``'source_excluded'``); without this
    check a job claimed before the deletion would recreate the deleted document, or put
    an archived record back into retrieval.
    """
    from app.services.source_lifecycle import ingest_job_cancelled

    if not ingest_job_cancelled(client, job_id):
        return False
    cleanup_document_version(client, org_id, doc_id)
    logger.info("rag_ingest_discarded_source_deleted org_id=%s job_id=%s", org_id, job_id)
    return True


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
            chunks = chunk_document_text(text or "", settings=settings, chunking=chunking)
            validate_chunks(chunks)

        _heartbeat_job(client, job_id, worker_id)
        content_sha256 = content_checksum(title, chunks)
        unchanged = _unchanged_active_document(
            settings, client, org_id, source_id, external_id, content_sha256
        )
        if unchanged:
            # Same text as the active version: nothing to re-chunk or re-embed.
            finalize_ingest_job(
                client,
                job_id=job_id,
                status="completed",
                document_id=unchanged,
                chunk_count=0,
                model=settings.embedding_model,
                dimension=settings.openai_embedding_dimension,
                clear_payload=True,
            )
            logger.info(
                "rag_ingest_unchanged_skipped org_id=%s job_id=%s document_id=%s",
                org_id,
                job_id,
                unchanged,
            )
            return
        doc = upsert_document(
            client,
            org_id=org_id,
            source_id=source_id,
            external_id=external_id,
            title=title,
            metadata={**(metadata if isinstance(metadata, dict) else {}), "content_sha256": content_sha256},
            is_active=False,
            environment_name=environment,
        )
        # One model call per document, not per chunk. Run with asyncio.run
        # because this worker is synchronous end to end and owns no event loop;
        # the synopsis helper returns "" rather than raising when the model is
        # unavailable, so enrichment degrades to its deterministic part instead
        # of failing an ingest.
        synopsis = ""
        if enrichment_enabled(settings):
            synopsis, _state = asyncio.run(
                build_document_synopsis(
                    text=text or "\n\n".join(chunks or []),
                    title=title or "",
                    settings=settings,
                    org_id=org_id,
                )
            )
            _heartbeat_job(client, job_id, worker_id)

        chunk_count = replace_chunks_and_embeddings(
            client,
            settings,
            org_id,
            source_id=source_id,
            document_id=str(doc["id"]),
            chunks=chunks,
            environment_name=environment,
            heartbeat_cb=lambda: _heartbeat_job(client, job_id, worker_id),
            title=title or "",
            synopsis=synopsis,
        )
        _heartbeat_job(client, job_id, worker_id)
        if _discard_if_source_deleted(client, org_id, job_id, str(doc["id"])):
            return
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
        # Checked again after activation: a removal that cancelled this job between the
        # first check and activation read the documents before this version existed.
        if _discard_if_source_deleted(client, org_id, job_id, str(doc["id"])):
            return
        finalize_ingest_job(
            client,
            job_id=job_id,
            status="completed",
            document_id=str(doc["id"]),
            chunk_count=chunk_count,
            model=settings.embedding_model,
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
            model=settings.embedding_model,
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
            model=settings.embedding_model,
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


def claimed_job_hold_reason(settings: Settings, client: Client, job: dict) -> str | None:
    """Why the standalone worker must hand ``job`` back instead of indexing it.

    * Jobs of orgs in RAG_WORKER_PILOT_ORG_IDS are pilot-scoped work: they get the
      same interlock as the in-process pilot (lifecycle prerequisites, provider
      revoke wired, customer-context opt-in), whichever process claims them.
    * With EXISTING_INGESTION_REQUIRES_LIFECYCLE=true (owner switch, default off),
      jobs of sources whose provider has no revoke call wired are held too.
    Otherwise None: the standalone worker indexes as it always has.
    """
    from app.schedulers.rag_ingest_pilot_scheduler import (
        _source_type,
        pilot_job_hold_reason,
        pilot_org_ids,
    )
    from app.services.ingestion_interlock import (
        existing_ingestion_gated,
        existing_ingestion_hold_reason,
    )

    if str(job.get("org_id") or "").lower() in pilot_org_ids(settings):
        return pilot_job_hold_reason(settings, client, job)
    if existing_ingestion_gated(settings):
        return existing_ingestion_hold_reason(settings, _source_type(client, job))
    return None


def run_worker_once(
    settings: Settings,
    client: Client,
    worker_id: str,
    visibility_timeout_s: int = 300,
) -> str:
    """One poll of the standalone worker: disabled | held | idle | released | processed."""
    from app.services.ingestion_interlock import existing_ingestion_hold_reason

    if settings.disable_ingestion:
        return "disabled"
    held = existing_ingestion_hold_reason(settings)
    if held:
        logger.warning("rag_worker_held reason=%s", held)
        return "held"
    job = _claim_job(client, worker_id=worker_id, visibility_timeout_s=visibility_timeout_s)
    if not job:
        return "idle"
    reason = claimed_job_hold_reason(settings, client, job)
    if reason:
        from app.schedulers.rag_ingest_pilot_scheduler import _release_job

        _release_job(client, {**job, "worker_id": job.get("worker_id") or worker_id}, reason)
        return "released"
    process_job(settings, client, job)
    return "processed"


def run_worker(
    poll_interval_s: int = 5,
    visibility_timeout_s: int = 300,
    worker_id: str | None = None,
) -> None:
    settings = get_settings()
    client = shared_service_client(settings, create_client)
    worker_id = worker_id or f"rag-worker-{uuid.uuid4().hex[:12]}"
    logger.info(
        "rag_worker_started poll_interval_s=%s visibility_timeout_s=%s worker_id=%s",
        poll_interval_s,
        visibility_timeout_s,
        worker_id,
    )
    while True:
        outcome = run_worker_once(settings, client, worker_id, visibility_timeout_s)
        if outcome != "processed":
            # A released job is reclaimed oldest-first, so back off instead of spinning.
            time.sleep(poll_interval_s)


if __name__ == "__main__":
    run_worker()

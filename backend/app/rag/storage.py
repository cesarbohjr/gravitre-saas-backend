"""Optional Supabase Storage retention for raw RAG upload bytes (STA-279)."""
from __future__ import annotations

import re
from typing import Any

from supabase import Client

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_SAFE_SEGMENT = re.compile(r"[^a-zA-Z0-9._-]+")


def _sanitize_segment(value: str, *, fallback: str = "file") -> str:
    cleaned = _SAFE_SEGMENT.sub("_", (value or "").strip()).strip("._")
    return cleaned or fallback


def build_rag_upload_path(
    *,
    org_id: str,
    environment_name: str,
    source_id: str,
    job_id: str,
    filename: str,
) -> str:
    """Object key: org/env/source/job/filename (org-scoped, no PII in path)."""
    safe_name = _sanitize_segment(filename, fallback="upload.bin")
    return "/".join(
        [
            _sanitize_segment(org_id, fallback="org"),
            _sanitize_segment(environment_name, fallback="default"),
            _sanitize_segment(source_id, fallback="source"),
            _sanitize_segment(job_id, fallback="job"),
            safe_name,
        ]
    )


def upload_raw_rag_file(
    client: Client,
    settings: Settings,
    *,
    org_id: str,
    environment_name: str,
    source_id: str,
    job_id: str,
    filename: str,
    data: bytes,
    content_type: str | None = None,
) -> dict[str, Any] | None:
    """Upload raw bytes to Supabase Storage when enabled. Returns metadata or None on skip/failure."""
    if not getattr(settings, "rag_store_raw_files", True):
        return None
    bucket = (getattr(settings, "rag_uploads_bucket", None) or "rag-uploads").strip()
    if not bucket or not data:
        return None

    path = build_rag_upload_path(
        org_id=org_id,
        environment_name=environment_name,
        source_id=source_id,
        job_id=job_id,
        filename=filename,
    )
    file_options: dict[str, Any] = {"upsert": "true"}
    if content_type:
        file_options["content-type"] = content_type

    try:
        client.storage.from_(bucket).upload(path, data, file_options=file_options)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "rag_raw_upload_failed org_id=%s job_id=%s path=%s error=%s",
            org_id,
            job_id,
            path,
            str(exc),
        )
        return None

    return {
        "storage_bucket": bucket,
        "storage_path": path,
        "storage_bytes": len(data),
    }

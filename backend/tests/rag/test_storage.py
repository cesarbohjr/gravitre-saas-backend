"""Tests for RAG raw upload storage helpers (STA-279)."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.config import Settings
from app.rag.storage import build_rag_upload_path, upload_raw_rag_file


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        rag_store_raw_files=True,
        rag_uploads_bucket="rag-uploads",
    )
    base.update(overrides)
    return Settings(**base)


def test_build_rag_upload_path_sanitizes_segments():
    path = build_rag_upload_path(
        org_id="org-1",
        environment_name="production",
        source_id="src-1",
        job_id="job-1",
        filename="Quarterly Plan.pdf",
    )
    assert path.startswith("org-1/production/src-1/job-1/")
    assert path.endswith(".pdf")


def test_upload_raw_rag_file_skips_when_disabled():
    client = MagicMock()
    result = upload_raw_rag_file(
        client,
        _settings(rag_store_raw_files=False),
        org_id="org-1",
        environment_name="production",
        source_id="src-1",
        job_id="job-1",
        filename="notes.txt",
        data=b"hello",
    )
    assert result is None
    client.storage.from_.assert_not_called()


def test_upload_raw_rag_file_returns_metadata():
    client = MagicMock()
    bucket = MagicMock()
    client.storage.from_.return_value = bucket

    result = upload_raw_rag_file(
        client,
        _settings(),
        org_id="org-1",
        environment_name="production",
        source_id="src-1",
        job_id="job-1",
        filename="notes.txt",
        data=b"hello",
        content_type="text/plain",
    )

    assert result is not None
    assert result["storage_bucket"] == "rag-uploads"
    assert result["storage_bytes"] == 5
    bucket.upload.assert_called_once()

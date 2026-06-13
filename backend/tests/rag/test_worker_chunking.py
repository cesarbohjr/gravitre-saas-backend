"""Worker ingest chunking (STA-171)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.config import Settings
from app.rag.worker import process_job


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
    )
    base.update(overrides)
    return Settings(**base)


def test_process_job_uses_semantic_chunking_for_text_payload():
    settings = _settings()
    client = MagicMock()
    job = {
        "id": "job-1",
        "org_id": "org-1",
        "source_id": "source-1",
        "environment": "default",
        "created_by": "user-1",
        "request_payload": {
            "text": "First paragraph about workflows.\n\nSecond paragraph about connectors.",
            "chunking": {"strategy": "semantic"},
        },
    }

    with patch("app.rag.worker.chunk_document_text", return_value=["chunk-a", "chunk-b"]) as chunk_mock:
        with patch("app.rag.worker.upsert_document", return_value={"id": "doc-1"}):
            with patch("app.rag.worker.replace_chunks_and_embeddings", return_value=2):
                with patch("app.rag.worker.activate_document"):
                    with patch("app.rag.worker.finalize_ingest_job"):
                        with patch("app.rag.worker.write_audit_event"):
                            process_job(settings, client, job)

    chunk_mock.assert_called_once()
    _, kwargs = chunk_mock.call_args
    assert kwargs.get("chunking", {}).get("strategy") == "semantic"

"""POST /api/rag-enhanced/ingest: DISABLE_INGESTION and org scoping of the source."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth.dependencies import require_admin
from app.config import Settings, get_settings
from app.main import app
from app.services.rag_service import RAGService, get_rag_service

ORG = "11111111-1111-4111-8111-111111111111"
SRC = "5f0c1c4e-0000-4000-8000-000000000001"
BODY = {"source_id": SRC, "content": "Customer contract terms", "environment": "production"}


def _settings(**kw) -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
        **kw,
    )


@pytest.fixture
def service():
    settings = _settings()
    with patch("app.services.rag_service.get_settings", return_value=settings):
        svc = RAGService()
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "admin-1"}, ORG)
    app.dependency_overrides[get_rag_service] = lambda: svc
    app.dependency_overrides[get_settings] = lambda: settings
    yield svc
    for dep in (require_admin, get_rag_service, get_settings):
        app.dependency_overrides.pop(dep, None)


async def test_disable_ingestion_answers_503_and_writes_nothing(async_client, service):
    app.dependency_overrides[get_settings] = lambda: _settings(disable_ingestion=True)
    with patch("app.services.rag_service.upsert_document") as upsert, patch(
        "app.services.rag_service.replace_chunks_and_embeddings"
    ) as replace:
        resp = await async_client.post("/api/rag-enhanced/ingest", json=BODY)
    assert resp.status_code == 503
    upsert.assert_not_called()
    replace.assert_not_called()


async def test_source_of_another_org_answers_404_and_writes_nothing(async_client, service):
    client = MagicMock()
    with patch("app.services.rag_service.get_supabase_client", return_value=client), patch(
        "app.services.rag_service.get_source", return_value=None
    ) as get_source, patch("app.services.rag_service.upsert_document") as upsert, patch(
        "app.services.rag_service.replace_chunks_and_embeddings"
    ) as replace:
        resp = await async_client.post("/api/rag-enhanced/ingest", json=BODY)
    assert resp.status_code == 404
    # Looked up in the caller's org and the requested environment only.
    get_source.assert_called_once_with(client, ORG, SRC, environment_name="production")
    upsert.assert_not_called()
    replace.assert_not_called()


async def test_source_of_this_org_is_indexed(async_client, service):
    with patch("app.services.rag_service.get_supabase_client", return_value=MagicMock()), patch(
        "app.services.rag_service.get_source", return_value={"id": SRC, "org_id": ORG}
    ), patch("app.services.rag_service.upsert_document", return_value={"id": "doc-1"}) as upsert, patch(
        "app.services.rag_service.chunk_document_text", return_value=["a", "b"]
    ), patch(
        "app.services.rag_service.build_document_synopsis", new=AsyncMock(return_value=("", None))
    ), patch("app.services.rag_service.replace_chunks_and_embeddings", return_value=2):
        resp = await async_client.post("/api/rag-enhanced/ingest", json=BODY)
    assert resp.status_code == 200
    assert resp.json()["total"] == 2
    assert upsert.call_args.kwargs["org_id"] == ORG


async def test_malformed_source_id_answers_404_without_a_lookup(async_client, service):
    with patch("app.services.rag_service.get_supabase_client") as get_client, patch(
        "app.services.rag_service.get_source"
    ) as get_source, patch("app.services.rag_service.upsert_document") as upsert:
        resp = await async_client.post("/api/rag-enhanced/ingest", json={**BODY, "source_id": "src-1' OR 1=1"})
    assert resp.status_code == 404
    get_client.assert_not_called()
    get_source.assert_not_called()
    upsert.assert_not_called()

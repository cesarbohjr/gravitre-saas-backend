"""POST /api/rag-enhanced/ingest against real PostgreSQL: org and environment scoping.

The route runs with the service-role client (RLS bypassed), so the only thing that
keeps one tenant's request from writing into another tenant's source is the explicit
(org, environment) source lookup. Each case drives the real route and service code
over a throwaway cluster and then counts rows: a refused request must leave every
table exactly as it was.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth.dependencies import require_admin
from app.config import Settings, get_settings
from app.main import app
from app.services.rag_service import RAGService, get_rag_service
from tests.db.pg_harness import pg_cluster, requires_pg
from tests.db.pg_rest import PgRestClient

pytestmark = requires_pg

ORG_A = "11111111-1111-4111-8111-111111111111"
ORG_B = "22222222-2222-4222-8222-222222222222"
SRC_A_PROD = "aaaaaaaa-0000-4000-8000-00000000000a"
SRC_A_STAGING = "aaaaaaaa-0000-4000-8000-00000000000b"
SRC_B_PROD = "bbbbbbbb-0000-4000-8000-00000000000a"
MISSING = "cccccccc-0000-4000-8000-00000000000a"

SCHEMA_SQL = f"""
CREATE TABLE public.organizations (id uuid PRIMARY KEY);
CREATE TABLE public.rag_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  title text NOT NULL, type text NOT NULL, metadata jsonb,
  environment text NOT NULL DEFAULT 'production',
  department_id uuid, agent_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.rag_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  source_id uuid NOT NULL REFERENCES public.rag_sources(id) ON DELETE CASCADE,
  external_id text, title text, metadata jsonb NOT NULL DEFAULT '{{}}',
  environment text NOT NULL DEFAULT 'production',
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO public.organizations VALUES ('{ORG_A}'), ('{ORG_B}');
INSERT INTO public.rag_sources (id, org_id, title, type, environment) VALUES
  ('{SRC_A_PROD}', '{ORG_A}', 'A prod', 'file', 'production'),
  ('{SRC_A_STAGING}', '{ORG_A}', 'A staging', 'file', 'staging'),
  ('{SRC_B_PROD}', '{ORG_B}', 'B prod', 'file', 'production');
"""


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(SCHEMA_SQL) as server:
        yield server


@pytest.fixture(autouse=True)
def _clean(pg):
    pg.psql("DELETE FROM public.rag_documents;")
    yield


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
def ingest(pg):
    """Admin of ORG_A posting through the real route, service and PostgreSQL."""
    settings = _settings()
    with patch("app.services.rag_service.get_settings", return_value=settings):
        svc = RAGService()
    client = PgRestClient(pg)
    replace = MagicMock(return_value=1)
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "admin-a"}, ORG_A)
    app.dependency_overrides[get_rag_service] = lambda: svc
    app.dependency_overrides[get_settings] = lambda: settings
    with patch("app.services.rag_service.get_supabase_client", return_value=client), patch(
        "app.services.rag_service.build_document_synopsis", new=AsyncMock(return_value=("", None))
    ), patch("app.services.rag_service.replace_chunks_and_embeddings", replace):
        yield {"client": client, "replace": replace, "service": svc}
    for dep in (require_admin, get_rag_service, get_settings):
        app.dependency_overrides.pop(dep, None)


def _docs(pg) -> list[tuple[str, str, str]]:
    out = pg.value(
        "SELECT coalesce(string_agg(org_id || '|' || source_id || '|' || environment, ';' ORDER BY created_at), '')"
        " FROM public.rag_documents;"
    )
    return [tuple(r.split("|")) for r in out.split(";") if r]


def _body(source_id: str, environment: str = "production") -> dict:
    return {"source_id": source_id, "content": "Customer contract terms", "environment": environment}


async def test_own_source_in_own_environment_is_written_to_own_org(async_client, pg, ingest):
    resp = await async_client.post("/api/rag-enhanced/ingest", json=_body(SRC_A_PROD))
    assert resp.status_code == 200
    assert _docs(pg) == [(ORG_A, SRC_A_PROD, "production")]
    assert ingest["replace"].call_args.kwargs["org_id"] == ORG_A

    resp = await async_client.post("/api/rag-enhanced/ingest", json=_body(SRC_A_STAGING, "staging"))
    assert resp.status_code == 200
    assert (ORG_A, SRC_A_STAGING, "staging") in _docs(pg)


@pytest.mark.parametrize(
    "source_id, environment",
    [
        (SRC_B_PROD, "production"),  # another tenant's source
        (SRC_B_PROD, "staging"),  # another tenant's source, other environment
        (SRC_A_STAGING, "production"),  # own source, wrong environment
        (SRC_A_PROD, "staging"),  # own source, wrong environment
        (MISSING, "production"),  # no such source
    ],
)
async def test_cross_tenant_and_cross_environment_answer_404_and_create_nothing(
    async_client, pg, ingest, source_id, environment
):
    before = pg.value("SELECT count(*) FROM public.rag_sources;")
    resp = await async_client.post("/api/rag-enhanced/ingest", json=_body(source_id, environment))
    assert resp.status_code == 404
    assert resp.json().get("error", resp.json().get("detail")) is not None
    assert _docs(pg) == []
    assert pg.value("SELECT count(*) FROM public.rag_sources;") == before
    ingest["replace"].assert_not_called()
    # The only statement that reached the database was the scoped lookup.
    assert len(ingest["client"].statements) == 1
    stmt = ingest["client"].statements[0]
    assert stmt.startswith("SELECT") and f"\"org_id\" = '{ORG_A}'" in stmt
    assert f"\"environment\" = '{environment}'" in stmt


async def test_malformed_source_id_answers_404_without_touching_the_database(async_client, pg, ingest):
    resp = await async_client.post("/api/rag-enhanced/ingest", json=_body("x' OR org_id <> '' --"))
    assert resp.status_code == 404
    assert ingest["client"].statements == []
    assert _docs(pg) == []


async def test_disable_ingestion_answers_503_without_touching_the_database(async_client, pg, ingest):
    app.dependency_overrides[get_settings] = lambda: _settings(disable_ingestion=True)
    resp = await async_client.post("/api/rag-enhanced/ingest", json=_body(SRC_A_PROD))
    assert resp.status_code == 503
    assert ingest["client"].statements == []
    assert _docs(pg) == []


async def test_disable_ingestion_in_the_service_settings_also_refuses(async_client, pg, ingest):
    # The route reads one Settings, the service another; either one refuses.
    ingest["service"].settings = _settings(disable_ingestion=True)
    resp = await async_client.post("/api/rag-enhanced/ingest", json=_body(SRC_A_PROD))
    assert resp.status_code == 503
    assert ingest["client"].statements == []
    assert _docs(pg) == []

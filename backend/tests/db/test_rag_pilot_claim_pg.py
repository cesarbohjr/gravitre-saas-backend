"""Phase 2D claim_rag_ingest_job_for_orgs against a real, throwaway PostgreSQL cluster."""
from __future__ import annotations

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg

MIGRATION = MIGRATIONS / "20261012024300_rag_ingest_pilot_claim.sql"
PILOT = "11111111-1111-4111-8111-111111111111"
OTHER = "33333333-3333-4333-8333-333333333333"

BOOTSTRAP_SQL = """
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE TABLE public.rag_ingest_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  source_id uuid NOT NULL DEFAULT gen_random_uuid(),
  external_id text,
  created_by uuid,
  environment text NOT NULL DEFAULT 'default',
  status text NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
  worker_id text,
  request_payload jsonb,
  started_at timestamptz,
  heartbeat_at timestamptz,
  updated_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON public.rag_ingest_jobs TO service_role;
"""


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(BOOTSTRAP_SQL, MIGRATION.read_text()) as server:
        yield server


@pytest.fixture(autouse=True)
def _seed(pg):
    pg.psql(
        "DELETE FROM public.rag_ingest_jobs;"
        f"INSERT INTO public.rag_ingest_jobs (org_id, status, external_id, created_at) VALUES"
        f" ('{OTHER}', 'queued', 'other-oldest', now() - interval '3 hours'),"
        f" ('{PILOT}', 'queued', 'pilot-1', now() - interval '2 hours'),"
        f" ('{PILOT}', 'running', 'pilot-stale', now() - interval '1 hour'),"
        f" ('{PILOT}', 'completed', 'pilot-done', now() - interval '4 hours');"
        "UPDATE public.rag_ingest_jobs SET heartbeat_at = now() - interval '1 hour' WHERE external_id = 'pilot-stale';"
    )
    yield


def _claim(pg, orgs: str) -> str:
    return pg.value(
        f"SELECT external_id || ':' || worker_id FROM public.claim_rag_ingest_job_for_orgs('w1', 300, {orgs});"
    )


def test_claims_only_listed_orgs_oldest_first_including_stale(pg):
    arr = f"ARRAY['{PILOT}']::uuid[]"
    assert _claim(pg, arr) == "pilot-1:w1"
    assert _claim(pg, arr) == "pilot-stale:w1"
    assert _claim(pg, arr) == ""
    assert pg.value("SELECT status FROM public.rag_ingest_jobs WHERE external_id = 'other-oldest';") == "queued"


@pytest.mark.parametrize("orgs", ["'{}'::uuid[]", "NULL"])
def test_empty_allowlist_claims_nothing(pg, orgs):
    assert _claim(pg, orgs) == ""
    assert pg.value("SELECT count(*) FROM public.rag_ingest_jobs WHERE worker_id IS NOT NULL;") == "0"


def test_only_service_role_may_execute(pg):
    for role in ("anon", "authenticated"):
        res = pg.psql(
            f"SET ROLE {role}; SELECT * FROM public.claim_rag_ingest_job_for_orgs('w', 300, ARRAY['{PILOT}']::uuid[]);",
            check=False,
        )
        assert res.returncode != 0 and "permission denied" in res.stderr

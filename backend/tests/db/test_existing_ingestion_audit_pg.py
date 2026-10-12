"""supabase/scripts/existing_ingestion_impact_audit.sql against real PostgreSQL.

Seeds two tenants, runs the audit file unchanged and checks the per-org counts, the
head-of-line check, that it writes nothing, and that its provider list matches the
code's (provider_revoke.SUPPORTED_VENDORS, ingestion_interlock.KNOWLEDGE_SYNC_VENDORS).
"""
from __future__ import annotations

import re

import pytest

from app.connectors.provider_revoke import SUPPORTED_VENDORS
from app.services.ingestion_interlock import KNOWLEDGE_SYNC_VENDORS
from tests.db.pg_harness import REPO_ROOT, pg_cluster, requires_pg

AUDIT = REPO_ROOT / "supabase" / "scripts" / "existing_ingestion_impact_audit.sql"

ORG_A = "11111111-1111-4111-8111-111111111111"
ORG_B = "22222222-2222-4222-8222-222222222222"

SCHEMA_SQL = f"""
CREATE TABLE public.organizations (id uuid PRIMARY KEY);
CREATE TABLE public.connectors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id),
  type text NOT NULL, vendor text, status text NOT NULL DEFAULT 'active', deleted_at timestamptz
);
CREATE TABLE public.rag_sources (
  id uuid PRIMARY KEY, org_id uuid NOT NULL REFERENCES public.organizations(id), type text NOT NULL
);
CREATE TABLE public.rag_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL, source_id uuid NOT NULL REFERENCES public.rag_sources(id) ON DELETE CASCADE
);
CREATE TABLE public.rag_ingest_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL, source_id uuid NOT NULL REFERENCES public.rag_sources(id) ON DELETE CASCADE,
  status text NOT NULL, created_at timestamptz NOT NULL
);
CREATE TABLE public.knowledge_sync_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL, connector_id uuid NOT NULL, status text NOT NULL
);
INSERT INTO public.organizations VALUES ('{ORG_A}'), ('{ORG_B}');
INSERT INTO public.connectors (org_id, type, vendor, status, deleted_at) VALUES
  ('{ORG_A}', 'notion', 'notion', 'active', NULL),
  ('{ORG_A}', 'hubspot', 'hubspot', 'active', NULL),
  ('{ORG_A}', 'confluence', 'confluence', 'paused', NULL),
  ('{ORG_A}', 'zendesk', 'zendesk', 'active', now()),     -- disconnected: not counted
  ('{ORG_A}', 'slack', 'slack', 'active', NULL),           -- no knowledge sync: not counted
  ('{ORG_B}', 'hubspot', 'hubspot', 'active', NULL);
INSERT INTO public.rag_sources (id, org_id, type) VALUES
  ('aaaaaaaa-0000-4000-8000-000000000001', '{ORG_A}', 'notion'),
  ('aaaaaaaa-0000-4000-8000-000000000002', '{ORG_A}', 'hubspot'),
  ('aaaaaaaa-0000-4000-8000-000000000003', '{ORG_A}', 'file'),
  ('bbbbbbbb-0000-4000-8000-000000000001', '{ORG_B}', 'hubspot');
INSERT INTO public.rag_documents (org_id, source_id) VALUES
  ('{ORG_A}', 'aaaaaaaa-0000-4000-8000-000000000001'),
  ('{ORG_A}', 'aaaaaaaa-0000-4000-8000-000000000001'),
  ('{ORG_A}', 'aaaaaaaa-0000-4000-8000-000000000002'),
  ('{ORG_A}', 'aaaaaaaa-0000-4000-8000-000000000003'),
  ('{ORG_B}', 'bbbbbbbb-0000-4000-8000-000000000001');
INSERT INTO public.rag_ingest_jobs (id, org_id, source_id, status, created_at) VALUES
  ('dddddddd-0000-4000-8000-000000000001', '{ORG_A}', 'aaaaaaaa-0000-4000-8000-000000000001', 'queued', '2026-10-01'),
  ('dddddddd-0000-4000-8000-000000000002', '{ORG_A}', 'aaaaaaaa-0000-4000-8000-000000000002', 'queued', '2026-10-02'),
  ('dddddddd-0000-4000-8000-000000000003', '{ORG_A}', 'aaaaaaaa-0000-4000-8000-000000000003', 'queued', '2026-10-03'),
  ('dddddddd-0000-4000-8000-000000000004', '{ORG_A}', 'aaaaaaaa-0000-4000-8000-000000000001', 'completed', '2026-09-01'),
  ('dddddddd-0000-4000-8000-000000000005', '{ORG_B}', 'bbbbbbbb-0000-4000-8000-000000000001', 'queued', '2026-10-04');
INSERT INTO public.knowledge_sync_jobs (org_id, connector_id, status) VALUES
  ('{ORG_A}', gen_random_uuid(), 'queued'),
  ('{ORG_A}', gen_random_uuid(), 'completed');
"""

COLUMNS = [
    "org_id",
    "live_knowledge_connectors",
    "scheduled_syncs_held_while_not_ready",
    "connectors_held_when_ready",
    "scheduled_syncs_held_when_ready",
    "held_vendors",
    "rag_sources",
    "rag_sources_held_when_ready",
    "non_connector_sources_held_when_ready",
    "rag_documents",
    "rag_documents_in_sources_held_when_ready",
    "queued_ingest_jobs_held_while_not_ready",
    "queued_ingest_jobs_held_when_ready",
    "open_knowledge_sync_jobs",
]


def _snapshot(pg) -> str:
    return pg.value(
        "SELECT (SELECT count(*) FROM public.connectors) || ',' || (SELECT count(*) FROM public.rag_sources)"
        " || ',' || (SELECT count(*) FROM public.rag_documents)"
        " || ',' || (SELECT string_agg(status, ',' ORDER BY id) FROM public.rag_ingest_jobs)"
        " || ',' || (SELECT string_agg(status, ',' ORDER BY status) FROM public.knowledge_sync_jobs);"
    )


@requires_pg
def test_audit_counts_per_org_and_flags_head_of_line_blocking():
    with pg_cluster(SCHEMA_SQL) as pg:
        before = _snapshot(pg)
        lines = pg.psql(AUDIT.read_text()).stdout.strip().splitlines()
        assert _snapshot(pg) == before

    per_org = {}
    head = None
    for line in lines:
        cells = line.split("|")
        if len(cells) == len(COLUMNS):
            per_org[cells[0]] = dict(zip(COLUMNS, cells, strict=True))
        elif len(cells) == 5:
            head = cells
    assert set(per_org) == {ORG_A, ORG_B}
    a = per_org[ORG_A]
    assert {k: a[k] for k in COLUMNS[1:]} == {
        "live_knowledge_connectors": "3",
        "scheduled_syncs_held_while_not_ready": "2",
        "connectors_held_when_ready": "2",
        "scheduled_syncs_held_when_ready": "1",
        "held_vendors": "confluence,notion",
        "rag_sources": "3",
        "rag_sources_held_when_ready": "2",
        "non_connector_sources_held_when_ready": "1",
        "rag_documents": "4",
        "rag_documents_in_sources_held_when_ready": "3",
        "queued_ingest_jobs_held_while_not_ready": "3",
        "queued_ingest_jobs_held_when_ready": "2",
        "open_knowledge_sync_jobs": "1",
    }
    b = per_org[ORG_B]
    assert {k: b[k] for k in COLUMNS[1:]} == {
        "live_knowledge_connectors": "1",
        "scheduled_syncs_held_while_not_ready": "1",
        "connectors_held_when_ready": "0",
        "scheduled_syncs_held_when_ready": "0",
        "held_vendors": "",
        "rag_sources": "1",
        "rag_sources_held_when_ready": "0",
        "non_connector_sources_held_when_ready": "0",
        "rag_documents": "1",
        "rag_documents_in_sources_held_when_ready": "0",
        "queued_ingest_jobs_held_while_not_ready": "1",
        "queued_ingest_jobs_held_when_ready": "0",
        "open_knowledge_sync_jobs": "0",
    }
    # Oldest queued job is Org A's Notion job: it would stall Org B's queue too.
    assert head == ["dddddddd-0000-4000-8000-000000000001", ORG_A, "notion", "t", "4"]


@requires_pg
def test_audit_runs_read_only():
    text = AUDIT.read_text()
    assert "BEGIN TRANSACTION READ ONLY;" in text and text.rstrip().endswith("ROLLBACK;")
    # A write slipped into the file would be refused by PostgreSQL inside that transaction.
    with pg_cluster(SCHEMA_SQL) as pg:
        res = pg.psql("BEGIN TRANSACTION READ ONLY; DELETE FROM public.rag_documents; ROLLBACK;", check=False)
        assert res.returncode != 0 and "read-only transaction" in res.stderr


def test_audit_provider_lists_match_the_code():
    text = AUDIT.read_text()
    blocks = re.findall(r"revocable\(vendor\) AS \(\s*VALUES(.*?)\n\)", text, flags=re.DOTALL)
    assert len(blocks) == 2
    for block in blocks:
        assert set(re.findall(r"\('([a-z0-9_]+)'\)", block)) == set(SUPPORTED_VENDORS)
    knowledge = re.search(r"knowledge_vendor\(vendor\) AS \(\s*VALUES(.*?)\n\)", text, flags=re.DOTALL)
    assert knowledge is not None
    assert set(re.findall(r"\('([a-z0-9_]+)'\)", knowledge.group(1))) == set(KNOWLEDGE_SYNC_VENDORS)


@pytest.mark.parametrize("vendor", sorted(KNOWLEDGE_SYNC_VENDORS))
def test_audit_treats_knowledge_vendors_like_the_interlock(vendor):
    from app.services.ingestion_interlock import provider_lifecycle_supported

    text = AUDIT.read_text()
    block = re.findall(r"revocable\(vendor\) AS \(\s*VALUES(.*?)\n\)", text, flags=re.DOTALL)[0]
    assert (f"('{vendor}')" in block) == provider_lifecycle_supported(vendor)

"""Phase 2B purge_connector_derived_data against a real, throwaway PostgreSQL cluster.

Creates the minimal shapes of the tables the purge touches (with the production
foreign keys and cascades), applies the outbox and purge migrations unchanged, and
checks what is removed, what is kept, dry runs, idempotency and grants.
"""
from __future__ import annotations

import json

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg

OUTBOX = MIGRATIONS / "20261012024141_domain_event_outbox.sql"
PURGE = MIGRATIONS / "20261012024200_source_lifecycle_purge.sql"
PROPOSALS = MIGRATIONS / "20261012030000_entity_merge_proposals.sql"

ORG = "11111111-1111-4111-8111-111111111111"
OTHER_ORG = "33333333-3333-4333-8333-333333333333"
HUBSPOT = "aaaaaaaa-0000-4000-8000-000000000001"
NOTION = "aaaaaaaa-0000-4000-8000-000000000002"
SRC_META = "bbbbbbbb-0000-4000-8000-000000000001"
SRC_CONFIG = "bbbbbbbb-0000-4000-8000-000000000002"
SRC_NOTION = "bbbbbbbb-0000-4000-8000-000000000003"
SRC_OTHER_ORG = "bbbbbbbb-0000-4000-8000-000000000004"
SRC_AFTER = "bbbbbbbb-0000-4000-8000-000000000005"
DISCONNECTED_AT = "2026-10-12 10:00:00+00"

BOOTSTRAP_SQL = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE SCHEMA auth;
CREATE TABLE auth.users (id uuid PRIMARY KEY);
CREATE TABLE public.organizations (id uuid PRIMARY KEY);
CREATE TABLE public.organization_members (org_id uuid, user_id uuid);
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT NULL::uuid $$;
CREATE TABLE public.workflow_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  workflow_id uuid, status text NOT NULL, completed_at timestamptz
);
CREATE TABLE public.connectors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  type text NOT NULL,
  vendor text,
  config jsonb NOT NULL DEFAULT '{{}}',
  status text NOT NULL DEFAULT 'connected',
  deleted_at timestamptz
);
CREATE TABLE public.rag_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  title text NOT NULL, type text NOT NULL, metadata jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.rag_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  source_id uuid NOT NULL REFERENCES public.rag_sources(id) ON DELETE CASCADE,
  external_id text
);
CREATE TABLE public.rag_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  document_id uuid NOT NULL REFERENCES public.rag_documents(id) ON DELETE CASCADE,
  source_id uuid NOT NULL REFERENCES public.rag_sources(id) ON DELETE CASCADE,
  content text NOT NULL
);
CREATE TABLE public.rag_embeddings (
  chunk_id uuid PRIMARY KEY REFERENCES public.rag_chunks(id) ON DELETE CASCADE,
  org_id uuid NOT NULL
);
CREATE TABLE public.rag_ingest_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id uuid NOT NULL REFERENCES public.rag_sources(id) ON DELETE CASCADE
);
CREATE TABLE public.agent_knowledge_references (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  connector_id uuid REFERENCES public.connectors(id) ON DELETE SET NULL,
  memory_summary text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.knowledge_sync_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  connector_id uuid NOT NULL REFERENCES public.connectors(id) ON DELETE CASCADE,
  status text NOT NULL, completed_at timestamptz, error_message text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.org_business_entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL, canonical_key text NOT NULL
);
CREATE TABLE public.org_business_entity_bindings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  entity_id uuid NOT NULL REFERENCES public.org_business_entities(id) ON DELETE CASCADE,
  system text NOT NULL, resource_type text NOT NULL, resource_id text NOT NULL
);
CREATE TABLE public.org_entity_resolution_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL, alias_normalized text NOT NULL, integration text NOT NULL DEFAULT ''
);
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
INSERT INTO public.organizations VALUES ('{ORG}'), ('{OTHER_ORG}');
"""


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(BOOTSTRAP_SQL, OUTBOX.read_text(), PURGE.read_text(), PROPOSALS.read_text()) as server:
        yield server


SEED_SQL = f"""
DELETE FROM public.org_entity_resolution_records;
DELETE FROM public.org_entity_merge_proposals;
DELETE FROM public.org_business_entities;
DELETE FROM public.knowledge_sync_jobs;
DELETE FROM public.agent_knowledge_references;
DELETE FROM public.rag_sources;
DELETE FROM public.connectors;
TRUNCATE public.source_purge_receipts, public.domain_event_outbox;

INSERT INTO public.connectors (id, org_id, type, vendor, config, deleted_at) VALUES
  ('{HUBSPOT}', '{ORG}', 'hubspot', 'hubspot',
   '{{"hubspot_rag_source_id": "{SRC_CONFIG}", "note": "not-a-uuid"}}', '{DISCONNECTED_AT}'),
  ('{NOTION}', '{ORG}', 'notion', 'notion', '{{}}', NULL);

INSERT INTO public.rag_sources (id, org_id, title, type, metadata, created_at) VALUES
  ('{SRC_META}', '{ORG}', 'HubSpot notes', 'hubspot', '{{"connector_id": "{HUBSPOT}"}}', '2026-10-01'),
  ('{SRC_CONFIG}', '{ORG}', 'HubSpot legacy', 'hubspot', '{{}}', '2026-10-01'),
  ('{SRC_NOTION}', '{ORG}', 'Notion', 'notion', '{{"connector_id": "{NOTION}"}}', '2026-10-01'),
  ('{SRC_OTHER_ORG}', '{OTHER_ORG}', 'Other org', 'hubspot', '{{"connector_id": "{HUBSPOT}"}}', '2026-10-01'),
  ('{SRC_AFTER}', '{ORG}', 'After reconnect', 'hubspot', '{{"connector_id": "{HUBSPOT}"}}', '2026-10-13');

INSERT INTO public.rag_documents (id, org_id, source_id, external_id)
  SELECT gen_random_uuid(), s.org_id, s.id, 'doc-' || g FROM public.rag_sources s, generate_series(1, 2) g;
INSERT INTO public.rag_chunks (id, org_id, document_id, source_id, content)
  SELECT gen_random_uuid(), d.org_id, d.id, d.source_id, 'text' FROM public.rag_documents d, generate_series(1, 3);
INSERT INTO public.rag_embeddings (chunk_id, org_id) SELECT id, org_id FROM public.rag_chunks;
INSERT INTO public.rag_ingest_jobs (source_id) SELECT id FROM public.rag_sources;

INSERT INTO public.agent_knowledge_references (org_id, connector_id, memory_summary, created_at) VALUES
  ('{ORG}', '{HUBSPOT}', 'Acme renewal notes', '2026-10-02'),
  ('{ORG}', '{NOTION}', 'Runbook', '2026-10-02');
INSERT INTO public.knowledge_sync_jobs (org_id, connector_id, status, created_at) VALUES
  ('{ORG}', '{HUBSPOT}', 'queued', '2026-10-11'),
  ('{ORG}', '{HUBSPOT}', 'completed', '2026-10-10'),
  ('{ORG}', '{NOTION}', 'queued', '2026-10-11');

INSERT INTO public.org_business_entities (id, org_id, canonical_key) VALUES
  ('cccccccc-0000-4000-8000-000000000001', '{ORG}', 'company:acme'),
  ('cccccccc-0000-4000-8000-000000000002', '{ORG}', 'company:globex'),
  ('cccccccc-0000-4000-8000-000000000003', '{ORG}', 'company:manual');
INSERT INTO public.org_business_entity_bindings (org_id, entity_id, system, resource_type, resource_id) VALUES
  ('{ORG}', 'cccccccc-0000-4000-8000-000000000001', 'hubspot', 'company', 'hs-1'),
  ('{ORG}', 'cccccccc-0000-4000-8000-000000000002', 'hubspot', 'company', 'hs-2'),
  ('{ORG}', 'cccccccc-0000-4000-8000-000000000002', 'zendesk', 'organization', 'zd-2'),
  ('{OTHER_ORG}', 'cccccccc-0000-4000-8000-000000000002', 'hubspot', 'company', 'hs-x');
INSERT INTO public.org_entity_merge_proposals (org_id, kind, system, resource_type, resource_id, reason, status) VALUES
  ('{ORG}', 'company', 'hubspot', 'company', 'hs-9', 'multiple_exact_matches', 'proposed'),
  ('{ORG}', 'company', 'hubspot', 'company', 'hs-8', 'multiple_exact_matches', 'rejected'),
  ('{ORG}', 'company', 'zendesk', 'organization', 'zd-9', 'multiple_exact_matches', 'proposed');
INSERT INTO public.org_entity_resolution_records (org_id, alias_normalized, integration) VALUES
  ('{ORG}', 'acme', 'hubspot'), ('{ORG}', 'runbook', 'notion'), ('{OTHER_ORG}', 'acme', 'hubspot');
"""


@pytest.fixture(autouse=True)
def _seed(pg):
    pg.psql(SEED_SQL)
    yield


def _purge(pg, *, dry_run: bool, vendor: str = "hubspot", connector: str = HUBSPOT) -> dict:
    out = pg.value(
        "SELECT public.purge_connector_derived_data("
        f"'{ORG}', '{connector}', '{vendor}', '{DISCONNECTED_AT}', {str(dry_run).lower()}, NULL);"
    )
    return json.loads(out)


def _count(pg, sql: str) -> int:
    return int(pg.value(sql))


def _sources(pg) -> set[str]:
    return set(filter(None, pg.value("SELECT string_agg(id::text, ',') FROM public.rag_sources;").split(",")))


def test_migration_is_idempotent(pg):
    pg.psql(PURGE.read_text())
    assert pg.value("SELECT count(*) FROM pg_proc WHERE proname = 'purge_connector_derived_data';") == "1"


def test_dry_run_counts_without_deleting(pg):
    counts = _purge(pg, dry_run=True)
    assert counts["rag_sources"] == 2  # metadata link + config key; not the reconnect, not other org
    assert counts["rag_documents"] == 4
    assert counts["rag_chunks"] == 12
    assert counts["agent_knowledge_references"] == 1
    assert counts["knowledge_sync_jobs_skipped"] == 1
    assert counts["entity_bindings"] == 2
    assert counts["entity_aliases"] == 1
    assert counts["entities"] == 1  # globex keeps its zendesk binding
    assert counts["vendor_shared"] is False
    assert len(_sources(pg)) == 5
    assert _count(pg, "SELECT count(*) FROM public.org_business_entity_bindings;") == 4
    receipt = json.loads(pg.value("SELECT row_to_json(r) FROM public.source_purge_receipts r;"))
    assert receipt["dry_run"] is True and receipt["counts"]["rag_sources"] == 2


def test_purge_removes_derived_data_and_keeps_everything_else(pg):
    _purge(pg, dry_run=False)
    assert _sources(pg) == {SRC_NOTION, SRC_OTHER_ORG, SRC_AFTER}
    # Cascades reached every derived row of the purged sources.
    for table in ("rag_documents", "rag_chunks", "rag_ingest_jobs"):
        left = _count(
            pg,
            f"SELECT count(*) FROM public.{table} WHERE source_id IN ('{SRC_META}', '{SRC_CONFIG}');",
        )
        assert left == 0, table
    assert _count(pg, "SELECT count(*) FROM public.rag_embeddings;") == 3 * 2 * 3
    assert _count(pg, f"SELECT count(*) FROM public.agent_knowledge_references WHERE connector_id = '{HUBSPOT}';") == 0
    assert _count(pg, f"SELECT count(*) FROM public.agent_knowledge_references WHERE connector_id = '{NOTION}';") == 1
    assert pg.value(
        f"SELECT string_agg(status, ',' ORDER BY status) FROM public.knowledge_sync_jobs WHERE connector_id = '{HUBSPOT}';"
    ) == "completed,skipped"
    assert pg.value(f"SELECT status FROM public.knowledge_sync_jobs WHERE connector_id = '{NOTION}';") == "queued"
    assert pg.value(
        "SELECT string_agg(system || ':' || org_id, ',' ORDER BY system) FROM public.org_business_entity_bindings;"
    ) == f"hubspot:{OTHER_ORG},zendesk:{ORG}"
    assert pg.value("SELECT string_agg(canonical_key, ',' ORDER BY canonical_key) FROM public.org_business_entities;") == (
        "company:globex,company:manual"  # manual entity had no bindings; never touched
    )
    assert pg.value(
        "SELECT string_agg(integration || ':' || org_id, ',' ORDER BY integration) FROM public.org_entity_resolution_records;"
    ) == f"hubspot:{OTHER_ORG},notion:{ORG}"
    # Open proposals about the vendor go; decided ones and other vendors stay.
    assert pg.value(
        "SELECT string_agg(resource_id, ',' ORDER BY resource_id) FROM public.org_entity_merge_proposals;"
    ) == "hs-8,zd-9"


def test_second_delivery_removes_nothing_and_keeps_first_receipt(pg):
    first = _purge(pg, dry_run=False)
    second = _purge(pg, dry_run=False)
    assert first["rag_sources"] == 2
    assert all(second[k] == 0 for k in second if k != "vendor_shared")
    rows = json.loads(pg.value("SELECT json_agg(r) FROM public.source_purge_receipts r WHERE NOT dry_run;"))
    assert len(rows) == 1 and rows[0]["counts"]["rag_sources"] == 2


def test_vendor_joins_kept_while_another_live_connector_of_that_vendor_exists(pg):
    pg.psql(f"INSERT INTO public.connectors (org_id, type, vendor) VALUES ('{ORG}', 'hubspot', 'hubspot');")
    counts = _purge(pg, dry_run=False)
    assert counts["vendor_shared"] is True
    assert counts["entity_bindings"] == 0 and counts["entity_aliases"] == 0
    assert _count(pg, "SELECT count(*) FROM public.org_business_entity_bindings;") == 4
    assert counts["rag_sources"] == 2  # the connector's own index still goes


def test_reconnected_connector_keeps_new_life(pg):
    pg.psql(f"UPDATE public.connectors SET deleted_at = NULL WHERE id = '{HUBSPOT}';")
    counts = _purge(pg, dry_run=False)
    assert counts["vendor_shared"] is True
    assert SRC_AFTER in _sources(pg)
    assert counts["rag_sources"] == 2


def test_hard_deleted_connector_still_purges_by_metadata(pg):
    pg.psql(f"DELETE FROM public.connectors WHERE id = '{HUBSPOT}';")
    counts = _purge(pg, dry_run=False)
    assert counts["rag_sources"] == 1  # config key is gone with the row; metadata link remains
    assert SRC_META not in _sources(pg)


def test_only_service_role_may_execute(pg):
    for role in ("anon", "authenticated"):
        res = pg.psql(
            f"SET ROLE {role}; SELECT public.purge_connector_derived_data("
            f"'{ORG}', '{HUBSPOT}', 'hubspot', now(), true, NULL);",
            check=False,
        )
        assert res.returncode != 0 and "permission denied" in res.stderr
        res = pg.psql(f"SET ROLE {role}; SELECT count(*) FROM public.source_purge_receipts;", check=False)
        assert res.returncode != 0 and "permission denied" in res.stderr
    ok = pg.psql(
        f"SET ROLE service_role; SELECT public.purge_connector_derived_data("
        f"'{ORG}', '{HUBSPOT}', 'hubspot', '{DISCONNECTED_AT}', true, NULL);"
    )
    assert ok.returncode == 0


def test_required_arguments(pg):
    res = pg.psql(
        f"SELECT public.purge_connector_derived_data('{ORG}', '{HUBSPOT}', 'hubspot', NULL, true, NULL);",
        check=False,
    )
    assert res.returncode != 0 and "required" in res.stderr


def test_disconnect_event_reaches_outbox_for_handler(pg):
    pg.psql(f"UPDATE public.connectors SET deleted_at = now() WHERE id = '{NOTION}';")
    payload = json.loads(
        pg.value("SELECT payload FROM public.domain_event_outbox WHERE event_type = 'source.disconnected' "
                 f"AND aggregate_id = '{NOTION}';")
    )
    assert payload["connector_id"] == NOTION and payload["connector_type"] == "notion"

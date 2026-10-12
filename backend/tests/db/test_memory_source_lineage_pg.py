"""purge_connector_memories against a real, throwaway PostgreSQL cluster.

Creates the minimal shape of agent_memories (then applies the real temporal
hardening migration on top of it), applies the Phase 2B purge migration and the
lineage migration unchanged, and checks dry runs, deletion scope by org, connector
and time, giving back a superseded older value, receipt merge, idempotency and grants.
"""
from __future__ import annotations

import json

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg

HARDENING = MIGRATIONS / "20260903120000_memory_hardening_temporal.sql"
PURGE = MIGRATIONS / "20261012010000_source_lifecycle_purge.sql"
LINEAGE = MIGRATIONS / "20261012070000_agent_memory_source_lineage.sql"

ORG = "11111111-1111-4111-8111-111111111111"
OTHER_ORG = "33333333-3333-4333-8333-333333333333"
HUBSPOT = "aaaaaaaa-0000-4000-8000-000000000001"
NOTION = "aaaaaaaa-0000-4000-8000-000000000002"
DISCONNECTED_AT = "2026-10-12 10:00:00+00"

M_HS_1 = "dddddddd-0000-4000-8000-000000000001"  # hubspot, before disconnect
M_HS_2 = "dddddddd-0000-4000-8000-000000000002"  # hubspot, before; superseded M_USER
M_HS_AFTER = "dddddddd-0000-4000-8000-000000000003"  # hubspot, after reconnect
M_NOTION = "dddddddd-0000-4000-8000-000000000004"
M_OTHER_ORG = "dddddddd-0000-4000-8000-000000000005"  # same connector id, other org
M_UNTAGGED = "dddddddd-0000-4000-8000-000000000006"
M_USER = "dddddddd-0000-4000-8000-000000000007"  # older user value replaced by M_HS_2
M_USER_B = "dddddddd-0000-4000-8000-000000000008"  # older value replaced by M_HS_B
M_HS_B = "dddddddd-0000-4000-8000-000000000009"  # hubspot; then replaced by M_LATER_B
M_LATER_B = "dddddddd-0000-4000-8000-00000000000a"  # current for key B, not from hubspot

BOOTSTRAP_SQL = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE SCHEMA auth;
CREATE TABLE auth.users (id uuid PRIMARY KEY);
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT NULL::uuid $$;
CREATE TABLE public.organizations (id uuid PRIMARY KEY);
CREATE TABLE public.organization_members (org_id uuid, user_id uuid);
CREATE TABLE public.connectors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  type text NOT NULL, vendor text, config jsonb NOT NULL DEFAULT '{{}}',
  deleted_at timestamptz
);
CREATE TABLE public.rag_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL, metadata jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.rag_documents (id uuid PRIMARY KEY, source_id uuid NOT NULL);
CREATE TABLE public.rag_chunks (id uuid PRIMARY KEY, source_id uuid NOT NULL);
-- Shape of 20260629120000 (+ is_active from 20260708160300) without pgvector.
CREATE TABLE public.agent_memories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  agent_id uuid,
  content text NOT NULL,
  category text NOT NULL DEFAULT 'fact',
  provenance text,
  confidence numeric(5, 2) NOT NULL DEFAULT 100,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.agent_memory_promotion_audit (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  memory_id uuid REFERENCES public.agent_memories(id) ON DELETE SET NULL
);
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
INSERT INTO public.organizations VALUES ('{ORG}'), ('{OTHER_ORG}');
"""


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(
        BOOTSTRAP_SQL,
        HARDENING.read_text(),
        PURGE.read_text(),
        LINEAGE.read_text(),
        "GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;",
    ) as server:
        yield server


SEED_SQL = f"""
DELETE FROM public.agent_memory_promotion_audit;
DELETE FROM public.agent_memory_history;
UPDATE public.agent_memories SET superseded_by = NULL;
DELETE FROM public.agent_memories;
DELETE FROM public.connectors;
TRUNCATE public.source_purge_receipts;

INSERT INTO public.connectors (id, org_id, type, vendor, deleted_at) VALUES
  ('{HUBSPOT}', '{ORG}', 'hubspot', 'hubspot', '{DISCONNECTED_AT}'),
  ('{NOTION}', '{ORG}', 'notion', 'notion', NULL);

INSERT INTO public.agent_memories
  (id, org_id, content, category, memory_key, is_current, valid_until, source_connector_id,
   source_record_ref, created_at, valid_from) VALUES
  ('{M_HS_1}', '{ORG}', 'Acme renews in March', 'episodic', NULL, true, NULL, '{HUBSPOT}',
   'deal:42', '2026-10-01', '2026-10-01'),
  ('{M_USER}', '{ORG}', 'ICP: 50-200 employees', 'preference', 'preference:icp', false,
   '2026-10-05', NULL, NULL, '2026-09-01', '2026-09-01'),
  ('{M_HS_2}', '{ORG}', 'ICP: 10-50 employees', 'preference', 'preference:icp', true, NULL,
   '{HUBSPOT}', NULL, '2026-10-05', '2026-10-05'),
  ('{M_USER_B}', '{ORG}', 'Tone: formal', 'preference', 'preference:tone', false,
   '2026-10-03', NULL, NULL, '2026-09-01', '2026-09-01'),
  ('{M_HS_B}', '{ORG}', 'Tone: casual', 'preference', 'preference:tone', false,
   '2026-10-04', '{HUBSPOT}', NULL, '2026-10-03', '2026-10-03'),
  ('{M_LATER_B}', '{ORG}', 'Tone: friendly', 'preference', 'preference:tone', true, NULL,
   NULL, NULL, '2026-10-04', '2026-10-04'),
  ('{M_HS_AFTER}', '{ORG}', 'Globex churned', 'episodic', NULL, true, NULL, '{HUBSPOT}',
   NULL, '2026-10-13', '2026-10-13'),
  ('{M_NOTION}', '{ORG}', 'Runbook step 3', 'procedural', NULL, true, NULL, '{NOTION}',
   NULL, '2026-10-01', '2026-10-01'),
  ('{M_OTHER_ORG}', '{OTHER_ORG}', 'Other org fact', 'fact', NULL, true, NULL, '{HUBSPOT}',
   NULL, '2026-10-01', '2026-10-01'),
  ('{M_UNTAGGED}', '{ORG}', 'Untagged fact', 'fact', NULL, true, NULL, NULL, NULL,
   '2026-10-01', '2026-10-01');

UPDATE public.agent_memories SET superseded_by = '{M_HS_2}' WHERE id = '{M_USER}';
UPDATE public.agent_memories SET superseded_by = '{M_HS_B}' WHERE id = '{M_USER_B}';
UPDATE public.agent_memories SET superseded_by = '{M_LATER_B}' WHERE id = '{M_HS_B}';

INSERT INTO public.agent_memory_history
  (memory_id, org_id, memory_key, category, content, valid_from, valid_until, superseded_by) VALUES
  ('{M_USER}', '{ORG}', 'preference:icp', 'preference', 'ICP: 50-200 employees', '2026-09-01',
   '2026-10-05', '{M_HS_2}'),
  ('{M_HS_B}', '{ORG}', 'preference:tone', 'preference', 'Tone: casual', '2026-10-03',
   '2026-10-04', '{M_LATER_B}');
INSERT INTO public.agent_memory_promotion_audit (org_id, memory_id) VALUES ('{ORG}', '{M_HS_1}');
"""


@pytest.fixture(autouse=True)
def _seed(pg):
    pg.psql(SEED_SQL)
    yield


def _derived_purge(pg, *, dry_run: bool) -> None:
    pg.psql(
        "SELECT public.purge_connector_derived_data("
        f"'{ORG}', '{HUBSPOT}', 'hubspot', '{DISCONNECTED_AT}', {str(dry_run).lower()}, NULL);"
    )


def _purge(pg, *, dry_run: bool, org: str = ORG, connector: str = HUBSPOT) -> dict:
    out = pg.value(
        "SELECT public.purge_connector_memories("
        f"'{org}', '{connector}', '{DISCONNECTED_AT}', {str(dry_run).lower()});"
    )
    return json.loads(out)


def _ids(pg) -> set[str]:
    return set(filter(None, pg.value("SELECT string_agg(id::text, ',') FROM public.agent_memories;").split(",")))


def _receipt(pg, *, dry_run: bool) -> dict:
    return json.loads(
        pg.value(f"SELECT counts FROM public.source_purge_receipts WHERE dry_run = {str(dry_run).lower()};")
    )


def test_migration_is_idempotent_and_adds_nullable_columns_and_partial_index(pg):
    pg.psql(LINEAGE.read_text())
    assert pg.value("SELECT count(*) FROM pg_proc WHERE proname = 'purge_connector_memories';") == "1"
    cols = pg.value(
        "SELECT string_agg(column_name || ':' || data_type || ':' || is_nullable, ',' ORDER BY column_name) "
        "FROM information_schema.columns WHERE table_name = 'agent_memories' "
        "AND column_name IN ('source_connector_id', 'source_record_ref');"
    )
    assert cols == "source_connector_id:uuid:YES,source_record_ref:text:YES"
    indexdef = pg.value(
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'idx_agent_memories_org_source_connector';"
    )
    assert "(org_id, source_connector_id)" in indexdef and "WHERE (source_connector_id IS NOT NULL)" in indexdef
    # No foreign key: lineage outlives the connector row.
    assert pg.value(
        "SELECT count(*) FROM pg_constraint c JOIN pg_attribute a ON a.attrelid = c.conrelid "
        "AND a.attnum = ANY (c.conkey) WHERE c.conrelid = 'public.agent_memories'::regclass "
        "AND c.contype = 'f' AND a.attname = 'source_connector_id';"
    ) == "0"


def test_dry_run_counts_without_deleting_and_merges_into_dry_run_receipt(pg):
    _derived_purge(pg, dry_run=True)
    counts = _purge(pg, dry_run=True)
    assert counts == {"agent_memories": 3, "agent_memories_restored": 1, "receipt_merged": True}
    assert len(_ids(pg)) == 10
    assert pg.value(f"SELECT is_current FROM public.agent_memories WHERE id = '{M_USER}';") == "f"
    receipt = _receipt(pg, dry_run=True)
    assert receipt["agent_memories"] == 3 and receipt["agent_memories_restored"] == 1
    assert receipt["rag_sources"] == 0  # the derived-data counts are kept alongside


def test_purge_deletes_only_this_org_connector_and_time(pg):
    _derived_purge(pg, dry_run=False)
    counts = _purge(pg, dry_run=False)
    assert counts["agent_memories"] == 3
    assert _ids(pg) == {M_USER, M_USER_B, M_LATER_B, M_HS_AFTER, M_NOTION, M_OTHER_ORG, M_UNTAGGED}
    # History of a purged row goes with it; the older value's own history stays.
    assert pg.value("SELECT string_agg(memory_id::text, ',') FROM public.agent_memory_history;") == M_USER
    assert pg.value("SELECT superseded_by IS NULL FROM public.agent_memory_history;") == "t"
    # Promotion audit is kept, unlinked.
    assert pg.value("SELECT count(*) FROM public.agent_memory_promotion_audit WHERE memory_id IS NULL;") == "1"


def test_purge_gives_back_the_value_a_purged_memory_replaced(pg):
    _purge(pg, dry_run=False)
    row = pg.value(
        f"SELECT is_current || ':' || coalesce(valid_until::text, '-') || ':' || coalesce(superseded_by::text, '-') "
        f"FROM public.agent_memories WHERE id = '{M_USER}';"
    )
    assert row == "true:-:-"
    # Key "tone" still has a current value not learned from HubSpot: nothing given back.
    assert pg.value(f"SELECT is_current FROM public.agent_memories WHERE id = '{M_USER_B}';") == "f"
    assert pg.value(
        "SELECT string_agg(id::text, ',') FROM public.agent_memories "
        "WHERE memory_key = 'preference:tone' AND is_current;"
    ) == M_LATER_B


def test_second_delivery_removes_nothing_and_keeps_first_receipt_count(pg):
    _derived_purge(pg, dry_run=False)
    first = _purge(pg, dry_run=False)
    second = _purge(pg, dry_run=False)
    assert first["agent_memories"] == 3 and first["receipt_merged"] is True
    assert second == {"agent_memories": 0, "agent_memories_restored": 0, "receipt_merged": False}
    assert _receipt(pg, dry_run=False)["agent_memories"] == 3


def test_receipt_of_other_mode_is_not_touched(pg):
    _derived_purge(pg, dry_run=True)
    counts = _purge(pg, dry_run=False)
    assert counts["receipt_merged"] is False
    assert "agent_memories" not in _receipt(pg, dry_run=True)


def test_without_a_receipt_still_purges(pg):
    counts = _purge(pg, dry_run=False)
    assert counts["agent_memories"] == 3 and counts["receipt_merged"] is False
    assert pg.value("SELECT count(*) FROM public.source_purge_receipts;") == "0"


def test_other_org_and_connector_scope(pg):
    assert _purge(pg, dry_run=False, org=OTHER_ORG)["agent_memories"] == 1
    assert M_OTHER_ORG not in _ids(pg) and M_HS_1 in _ids(pg)
    assert _purge(pg, dry_run=False, connector=NOTION)["agent_memories"] == 1
    assert M_NOTION not in _ids(pg)


def test_hard_deleted_connector_still_purges_by_lineage(pg):
    pg.psql(f"DELETE FROM public.connectors WHERE id = '{HUBSPOT}';")
    assert _purge(pg, dry_run=False)["agent_memories"] == 3


def test_only_service_role_may_execute(pg):
    for role in ("anon", "authenticated"):
        res = pg.psql(
            f"SET ROLE {role}; SELECT public.purge_connector_memories('{ORG}', '{HUBSPOT}', now(), true);",
            check=False,
        )
        assert res.returncode != 0 and "permission denied" in res.stderr
    assert pg.value(
        "SELECT has_function_privilege('public', "
        "'public.purge_connector_memories(uuid, uuid, timestamptz, boolean)', 'EXECUTE');"
    ) == "f"
    ok = pg.psql(
        f"SET ROLE service_role; SELECT public.purge_connector_memories('{ORG}', '{HUBSPOT}', "
        f"'{DISCONNECTED_AT}', true);"
    )
    assert ok.returncode == 0


def test_required_arguments(pg):
    res = pg.psql(
        f"SELECT public.purge_connector_memories('{ORG}', '{HUBSPOT}', NULL, true);",
        check=False,
    )
    assert res.returncode != 0 and "required" in res.stderr

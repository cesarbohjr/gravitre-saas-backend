"""The storage migration (20261020081535_storage_retention_metering and its parts) against a real, throwaway PostgreSQL cluster.

Minimal shapes of the tables the functions read (audit, telemetry, RAG, memories,
conversations, storage), the migration applied unchanged, then: floors, legal hold,
approval rows kept, bounded oldest-first batches, archive-mode id deletes, the storage
meter's proportional method, grants and the snapshot RLS policy.
"""
from __future__ import annotations

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg

# Prod stamped the storage migration in parts; applied here in version order.
MIGRATION_FILES = [
    "20261020081535_storage_retention_metering.sql",
    "20261020081624_storage_retention_receipts.sql",
    "20261020081826_storage_retention_floor.sql",
    "20261020081844_storage_retention_candidates.sql",
    "20261020081902_storage_retention_fetch_batch.sql",
    "20261020082113_storage_usage_snapshots.sql",
    "20261020082133_storage_usage_meter.sql",
    "20261020082154_storage_byo_targets.sql",
    "20261020090000_storage_retention_delete_batch.sql",
]
MIGRATION_SQL = "\n".join((MIGRATIONS / name).read_text() for name in MIGRATION_FILES)

ORG = "11111111-1111-4111-8111-111111111111"
OTHER_ORG = "33333333-3333-4333-8333-333333333333"
HELD_ORG = "55555555-5555-4555-8555-555555555555"
MEMBER = "77777777-7777-4777-8777-777777777777"

BOOTSTRAP_SQL = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE SCHEMA auth;
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE
  AS $$ SELECT nullif(current_setting('test.uid', true), '')::uuid $$;
CREATE TABLE public.organizations (id uuid PRIMARY KEY);
CREATE TABLE public.organization_members (org_id uuid, user_id uuid);
CREATE TABLE public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  action text NOT NULL, details jsonb NOT NULL DEFAULT '{{}}',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON public.audit_logs (created_at DESC);
CREATE TABLE public.audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  action text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.model_calls (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL, created_at timestamptz DEFAULT now()
);
CREATE TABLE public.guardrail_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL, created_at timestamptz DEFAULT now()
);
CREATE TABLE public.rag_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL, content text NOT NULL
);
CREATE TABLE public.agent_memories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL, content text NOT NULL
);
CREATE TABLE public.knowledge_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), content text NOT NULL
);
CREATE SCHEMA storage;
CREATE TABLE storage.buckets (id text PRIMARY KEY, name text NOT NULL, public boolean DEFAULT false);
CREATE TABLE storage.objects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  bucket_id text, name text, metadata jsonb
);
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT SELECT ON public.organization_members TO authenticated;
INSERT INTO public.organizations VALUES ('{ORG}'), ('{OTHER_ORG}'), ('{HELD_ORG}');
INSERT INTO public.organization_members VALUES ('{ORG}', '{MEMBER}');
"""


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(BOOTSTRAP_SQL, MIGRATION_SQL) as server:
        yield server


SEED_SQL = f"""
TRUNCATE public.audit_logs, public.audit_events, public.model_calls, public.rag_chunks,
  public.agent_memories, public.knowledge_chunks, public.org_legal_holds,
  public.org_storage_usage_snapshots;
DELETE FROM storage.objects;
-- ORG: 5 old ordinary rows (oldest first by day), 1 old approval row, 2 recent rows.
INSERT INTO public.audit_logs (org_id, action, created_at)
  SELECT '{ORG}', 'workflow.updated', now() - make_interval(days => 400 + g) FROM generate_series(1, 5) g;
INSERT INTO public.audit_logs (org_id, action, created_at) VALUES
  ('{ORG}', 'workflow.execute.approval_recorded', now() - interval '500 days'),
  ('{ORG}', 'workflow.execute.REJECTED', now() - interval '500 days'),
  ('{ORG}', 'workflow.updated', now() - interval '10 days'),
  ('{ORG}', 'workflow.updated', now() - interval '364 days');
INSERT INTO public.audit_logs (org_id, action, created_at)
  SELECT '{OTHER_ORG}', 'connector.synced', now() - interval '450 days' FROM generate_series(1, 3);
INSERT INTO public.audit_logs (org_id, action, created_at)
  SELECT '{HELD_ORG}', 'connector.synced', now() - interval '450 days' FROM generate_series(1, 4);
INSERT INTO public.org_legal_holds (org_id, reason) VALUES ('{HELD_ORG}', 'litigation');
INSERT INTO public.org_legal_holds (org_id, reason, released_at) VALUES ('{OTHER_ORG}', 'old', now());
INSERT INTO public.model_calls (org_id, created_at) VALUES
  ('{ORG}', now() - interval '401 days'), ('{ORG}', now() - interval '200 days'), ('{ORG}', NULL);
"""


@pytest.fixture(autouse=True)
def _seed(pg):
    pg.psql(SEED_SQL)
    yield


def _rows(pg, sql: str) -> list[list[str]]:
    out = pg.value(sql)
    return [line.split("|") for line in out.splitlines() if line]


def _int(pg, sql: str) -> int:
    return int(pg.value(sql))


def test_migration_is_idempotent(pg):
    pg.psql(MIGRATION_SQL)
    assert _int(pg, "SELECT count(*) FROM storage.buckets WHERE id = 'audit-archive' AND NOT public") == 1


def test_cutoff_inside_floor_and_unknown_tables_are_refused(pg):
    for table, days in (("audit_logs", 364), ("audit_events", 300), ("model_calls", 399)):
        res = pg.psql(
            f"SELECT * FROM public.data_retention_candidates('{table}', now() - interval '{days} days');",
            check=False,
        )
        assert res.returncode != 0 and "floor" in res.stderr, table
    res = pg.psql(
        "SELECT public.data_retention_delete_batch('guardrail_events', "
        f"'{ORG}', now() - interval '900 days', 10);",
        check=False,
    )
    assert res.returncode != 0 and "not eligible" in res.stderr
    res = pg.psql("SELECT * FROM public.data_retention_candidates('organizations', now() - interval '900 days');",
                  check=False)
    assert res.returncode != 0


def test_candidates_skip_held_orgs_and_approval_rows(pg):
    rows = _rows(pg, "SELECT org_id, row_count FROM public.data_retention_candidates("
                     "'audit_logs', now() - interval '365 days');")
    assert dict(rows) == {ORG: "5", OTHER_ORG: "3"}  # released hold does not count


def test_delete_batch_is_bounded_oldest_first_and_keeps_protected_rows(pg):
    cutoff = "now() - interval '365 days'"
    oldest = pg.value(f"SELECT min(created_at) FROM public.audit_logs WHERE org_id = '{ORG}' "
                      "AND action = 'workflow.updated'")
    assert _int(pg, f"SELECT public.data_retention_delete_batch('audit_logs', '{ORG}', {cutoff}, 2);") == 2
    assert _int(pg, f"SELECT count(*) FROM public.audit_logs WHERE created_at = '{oldest}'") == 0
    assert _int(pg, f"SELECT public.data_retention_delete_batch('audit_logs', '{ORG}', {cutoff}, 10);") == 3
    assert _int(pg, f"SELECT public.data_retention_delete_batch('audit_logs', '{ORG}', {cutoff}, 10);") == 0
    # approval, rejection, 10-day and 364-day rows remain; other org untouched.
    assert _int(pg, f"SELECT count(*) FROM public.audit_logs WHERE org_id = '{ORG}'") == 4
    assert _int(pg, f"SELECT count(*) FROM public.audit_logs WHERE org_id = '{OTHER_ORG}'") == 3


def test_legal_hold_blocks_delete_and_fetch(pg):
    cutoff = "now() - interval '365 days'"
    assert _int(pg, f"SELECT public.data_retention_delete_batch('audit_logs', '{HELD_ORG}', {cutoff}, 100);") == 0
    assert _int(pg, f"SELECT count(*) FROM public.data_retention_fetch_batch('audit_logs', '{HELD_ORG}', "
                    f"{cutoff}, 100);") == 0
    assert _int(pg, f"SELECT count(*) FROM public.audit_logs WHERE org_id = '{HELD_ORG}'") == 4


def test_archive_mode_fetches_then_deletes_only_matching_ids(pg):
    cutoff = "now() - interval '365 days'"
    ids = pg.value(
        f"SELECT string_agg(r->>'id', ',') FROM public.data_retention_fetch_batch('audit_logs', '{ORG}', "
        f"{cutoff}, 3) r;"
    ).split(",")
    assert len(ids) == 3
    recent = pg.value(f"SELECT id FROM public.audit_logs WHERE org_id = '{ORG}' "
                      "AND created_at > now() - interval '30 days'")
    approval = pg.value("SELECT id FROM public.audit_logs WHERE action LIKE '%approval%'")
    arr = "ARRAY[" + ",".join(f"'{i}'::uuid" for i in [*ids, recent, approval]) + "]"
    deleted = _int(pg, f"SELECT public.data_retention_delete_batch('audit_logs', '{ORG}', {cutoff}, 10, {arr});")
    assert deleted == 3
    assert _int(pg, f"SELECT count(*) FROM public.audit_logs WHERE id IN ('{recent}', '{approval}')") == 2


def test_model_calls_floor_and_null_created_at(pg):
    rows = _rows(pg, "SELECT org_id, row_count FROM public.data_retention_candidates("
                     "'model_calls', now() - interval '400 days');")
    assert rows == [[ORG, "1"]]


def test_one_running_retention_run_at_a_time(pg):
    pg.psql("TRUNCATE public.data_retention_runs; INSERT INTO public.data_retention_runs (dry_run) VALUES (true);")
    res = pg.psql("INSERT INTO public.data_retention_runs (dry_run) VALUES (false);", check=False)
    assert res.returncode != 0
    pg.psql("UPDATE public.data_retention_runs SET status = 'completed';"
            "INSERT INTO public.data_retention_runs (dry_run) VALUES (false);")


def test_storage_meter_splits_relation_size_by_row_share(pg):
    pg.psql(f"""
      INSERT INTO public.rag_chunks (org_id, content)
        SELECT '{ORG}', repeat('x', 200) FROM generate_series(1, 30);
      INSERT INTO public.rag_chunks (org_id, content)
        SELECT '{OTHER_ORG}', repeat('x', 200) FROM generate_series(1, 10);
      INSERT INTO public.agent_memories (org_id, content) VALUES ('{ORG}', 'm');
      INSERT INTO public.knowledge_chunks (content) VALUES ('platform');
      INSERT INTO storage.objects (bucket_id, name, metadata) VALUES
        ('rag-uploads', '{ORG}/production/s/j/a.pdf', '{{"size": 1000}}'),
        ('rag-uploads', '{ORG}/production/s/j/b.pdf', '{{"size": "250"}}'),
        ('audit-archive', '{ORG}/audit_logs/x.jsonl.gz', '{{"size": 40}}'),
        ('rag-uploads', 'not-an-org/x', '{{"size": 99}}');
      ANALYZE;
    """)
    size = _int(pg, "SELECT pg_total_relation_size('public.rag_chunks')")
    rows = _rows(pg, "SELECT org_id, category, source, bytes, row_count FROM public.compute_org_storage_usage(NULL) "
                     "ORDER BY 1, 2, 3")
    by_key = {(r[0], r[2]): (r[1], int(r[3]), int(r[4])) for r in rows}
    assert by_key[(ORG, "rag_chunks")] == ("knowledge", round(size * 30 / 40), 30)
    assert by_key[(OTHER_ORG, "rag_chunks")] == ("knowledge", round(size * 10 / 40), 10)
    assert by_key[(ORG, "agent_memories")][0] == "memories"
    assert by_key[(ORG, "storage.objects:rag-uploads")] == ("files", 1250, 2)
    assert by_key[(ORG, "storage.objects:audit-archive")] == ("audit", 40, 1)
    assert not any(r[2] == "knowledge_chunks" for r in rows)  # platform table, no org_id
    only = _rows(pg, f"SELECT DISTINCT org_id FROM public.compute_org_storage_usage('{OTHER_ORG}')")
    assert only == [[OTHER_ORG]]


def test_functions_are_service_role_only(pg):
    for sig in (
        "public.compute_org_storage_usage(uuid)",
        "public.data_retention_candidates(text, timestamptz)",
        "public.data_retention_fetch_batch(text, uuid, timestamptz, int)",
        "public.data_retention_delete_batch(text, uuid, timestamptz, int, uuid[])",
    ):
        for role in ("anon", "authenticated"):
            assert pg.value(f"SELECT has_function_privilege('{role}', '{sig}', 'EXECUTE')") == "f", (role, sig)
        assert pg.value(f"SELECT has_function_privilege('service_role', '{sig}', 'EXECUTE')") == "t", sig
    for table in ("org_storage_targets", "org_legal_holds", "data_retention_runs"):
        assert pg.value(f"SELECT has_table_privilege('authenticated', 'public.{table}', 'SELECT')") == "f", table


def test_snapshot_rls_members_read_only_their_org(pg):
    pg.psql(f"""
      INSERT INTO public.org_storage_usage_snapshots (org_id, total_bytes) VALUES ('{ORG}', 10), ('{OTHER_ORG}', 20);
    """)
    out = pg.value(f"""
      SET ROLE authenticated; SET test.uid = '{MEMBER}';
      SELECT string_agg(total_bytes::text, ',') FROM public.org_storage_usage_snapshots;
    """)
    assert out == "10"
    res = pg.psql(f"""
      SET ROLE authenticated; SET test.uid = '{MEMBER}';
      INSERT INTO public.org_storage_usage_snapshots (org_id, total_bytes) VALUES ('{ORG}', 1);
    """, check=False)
    assert res.returncode != 0
    dup = pg.psql(f"INSERT INTO public.org_storage_usage_snapshots (org_id, total_bytes) VALUES ('{ORG}', 1);",
                  check=False)
    assert dup.returncode != 0  # once per org per day; the writer upserts

"""Deleted sources and disconnected connectors stop being retrievable (real PostgreSQL).

Applies ``20261013030000_retrieval_excludes_dead_sources.sql`` unchanged on top of
the RAG table shapes and checks, through the real ``rag_search`` and triggers:

* a soft-deleted source's chunks never come back from vector search, and its
  documents are deactivated in the same transaction;
* disconnecting a connector deactivates documents of the sources it created at or
  before the disconnect, but not sources created after (a reconnect) or still used
  by another live connector;
* the backfill deactivates what was already dead when the migration ran.

Needs pgvector (rag_search takes a vector); skips when the extension is missing.
"""
from __future__ import annotations

import pytest

from tests.db.pg_harness import MIGRATIONS, PG_BIN, pg_cluster, requires_pg

MIGRATION = MIGRATIONS / "20261013030000_retrieval_excludes_dead_sources.sql"

ORG = "11111111-1111-4111-8111-111111111111"
CONN = "22222222-2222-4222-8222-222222222222"
OTHER_CONN = "33333333-3333-4333-8333-333333333333"


def _pgvector_available() -> bool:
    if PG_BIN is None:
        return False
    share = PG_BIN.parent.parent.parent.parent / "share" / "postgresql" / PG_BIN.parent.name / "extension"
    return (share / "vector.control").exists()


pytestmark = [
    requires_pg,
    pytest.mark.skipif(not _pgvector_available(), reason="pgvector extension not installed"),
]

VEC = "[" + ",".join(["0.1"] * 1536) + "]"

BOOTSTRAP_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE TABLE public.connectors (
  id uuid PRIMARY KEY, org_id uuid NOT NULL, type text NOT NULL DEFAULT 'gmail',
  config jsonb NOT NULL DEFAULT '{{}}', status text, deleted_at timestamptz
);
CREATE TABLE public.rag_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, title text,
  environment text NOT NULL DEFAULT 'default', metadata jsonb NOT NULL DEFAULT '{{}}',
  department_id uuid, agent_id uuid, deleted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.rag_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL,
  source_id uuid NOT NULL REFERENCES public.rag_sources(id) ON DELETE CASCADE,
  title text, environment text NOT NULL DEFAULT 'default', is_active boolean NOT NULL DEFAULT true
);
CREATE TABLE public.rag_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL,
  source_id uuid NOT NULL REFERENCES public.rag_sources(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES public.rag_documents(id) ON DELETE CASCADE,
  chunk_index int NOT NULL DEFAULT 0, content text, environment text NOT NULL DEFAULT 'default'
);
CREATE TABLE public.rag_embeddings (
  chunk_id uuid PRIMARY KEY REFERENCES public.rag_chunks(id) ON DELETE CASCADE,
  org_id uuid NOT NULL, environment text NOT NULL DEFAULT 'default', embedding vector(1536)
);
INSERT INTO public.connectors (id, org_id) VALUES ('{CONN}', '{ORG}'), ('{OTHER_CONN}', '{ORG}');
"""


def _source(pg, title: str, *, connector: str | None = None, created: str = "now()") -> str:
    meta = f"jsonb_build_object('connector_id', '{connector}')" if connector else "'{}'::jsonb"
    sid = pg.value(
        f"INSERT INTO public.rag_sources (org_id, title, metadata, created_at) "
        f"VALUES ('{ORG}', '{title}', {meta}, {created}) RETURNING id;"
    )
    did = pg.value(
        f"INSERT INTO public.rag_documents (org_id, source_id, title) VALUES ('{ORG}', '{sid}', '{title}') RETURNING id;"
    )
    cid = pg.value(
        f"INSERT INTO public.rag_chunks (org_id, source_id, document_id, content) "
        f"VALUES ('{ORG}', '{sid}', '{did}', '{title} text') RETURNING id;"
    )
    pg.psql(f"INSERT INTO public.rag_embeddings (chunk_id, org_id, embedding) VALUES ('{cid}', '{ORG}', '{VEC}');")
    return sid


def _search_titles(pg) -> set[str]:
    out = pg.value(
        f"SELECT coalesce(string_agg(source_title, ','), '') FROM public.rag_search('{ORG}', '{VEC}', 50);"
    )
    return set(filter(None, out.split(",")))


def _active(pg, sid: str) -> str:
    return pg.value(f"SELECT bool_and(is_active)::text FROM public.rag_documents WHERE source_id = '{sid}';")


@pytest.fixture()
def pg():
    with pg_cluster(BOOTSTRAP_SQL) as server:
        yield server


def test_backfill_deactivates_already_dead_sources(pg):
    pg.psql(f"UPDATE public.connectors SET deleted_at = now() - interval '1 day' WHERE id = '{OTHER_CONN}';")
    deleted = _source(pg, "deleted")
    pg.psql(f"UPDATE public.rag_sources SET deleted_at = now() WHERE id = '{deleted}';")  # before the trigger exists
    orphan = _source(pg, "from_disconnected", connector=OTHER_CONN, created="now() - interval '2 days'")
    live = _source(pg, "live")
    result = pg.psql(MIGRATION.read_text())
    assert "deleted_source_documents=1 disconnected_connector_documents=1" in result.stderr
    assert _active(pg, deleted) == "false"
    assert _active(pg, orphan) == "false"
    assert _active(pg, live) == "true"
    assert _search_titles(pg) == {"live"}


def test_deleted_source_disappears_from_search_at_once(pg):
    pg.psql(MIGRATION.read_text())
    keep = _source(pg, "keep")
    drop = _source(pg, "drop")
    assert _search_titles(pg) == {"keep", "drop"}
    pg.psql(f"UPDATE public.rag_sources SET deleted_at = now() WHERE id = '{drop}';")
    assert _search_titles(pg) == {"keep"}
    assert _active(pg, drop) == "false"
    assert _active(pg, keep) == "true"


def test_rag_search_filters_deleted_source_even_if_documents_were_active(pg):
    """Belt and braces: rag_search itself requires a live source."""
    pg.psql(MIGRATION.read_text())
    sid = _source(pg, "sneaky")
    pg.psql("ALTER TABLE public.rag_sources DISABLE TRIGGER rag_sources_deactivate_documents_on_delete;")
    pg.psql(f"UPDATE public.rag_sources SET deleted_at = now() WHERE id = '{sid}';")
    assert _active(pg, sid) == "true"
    assert _search_titles(pg) == set()


def test_disconnect_deactivates_only_that_connectors_earlier_sources(pg):
    pg.psql(MIGRATION.read_text())
    before = _source(pg, "before", connector=CONN, created="now() - interval '1 hour'")
    unrelated = _source(pg, "unrelated", connector=OTHER_CONN, created="now() - interval '1 hour'")
    manual = _source(pg, "manual", created="now() - interval '1 hour'")
    pg.psql(f"UPDATE public.connectors SET deleted_at = now(), status = 'disconnected' WHERE id = '{CONN}';")
    after = _source(pg, "after_reconnect", connector=CONN, created="now() + interval '1 minute'")
    assert _active(pg, before) == "false"
    assert _active(pg, unrelated) == "true"
    assert _active(pg, manual) == "true"
    assert _active(pg, after) == "true"
    assert _search_titles(pg) == {"unrelated", "manual", "after_reconnect"}


def test_disconnect_follows_config_source_keys(pg):
    pg.psql(MIGRATION.read_text())
    sid = _source(pg, "configured", created="now() - interval '1 hour'")
    pg.psql(f"UPDATE public.connectors SET config = jsonb_build_object('gmail_rag_source_id', '{sid}') WHERE id = '{CONN}';")
    pg.psql(f"UPDATE public.connectors SET deleted_at = now() WHERE id = '{CONN}';")
    assert _active(pg, sid) == "false"


def test_source_shared_with_a_live_connector_stays_active(pg):
    pg.psql(MIGRATION.read_text())
    sid = _source(pg, "shared", created="now() - interval '1 hour'")
    pg.psql(
        f"UPDATE public.connectors SET config = jsonb_build_object('gmail_rag_source_id', '{sid}') "
        f"WHERE id IN ('{CONN}', '{OTHER_CONN}');"
    )
    pg.psql(f"UPDATE public.connectors SET deleted_at = now() WHERE id = '{CONN}';")
    assert _active(pg, sid) == "true"
    assert "shared" in _search_titles(pg)


def test_second_disconnect_update_does_not_refire(pg):
    pg.psql(MIGRATION.read_text())
    pg.psql(f"UPDATE public.connectors SET deleted_at = now() - interval '5 minutes' WHERE id = '{CONN}';")
    # A source created later and an update that keeps the connector deleted.
    later = _source(pg, "later", connector=CONN)
    pg.psql(f"UPDATE public.connectors SET deleted_at = now() WHERE id = '{CONN}';")
    assert _active(pg, later) == "true"


def test_migration_is_idempotent(pg):
    pg.psql(MIGRATION.read_text())
    pg.psql(MIGRATION.read_text())
    assert pg.value(
        "SELECT count(*) FROM pg_trigger WHERE tgname IN "
        "('rag_sources_deactivate_documents_on_delete', 'connectors_deactivate_documents_on_disconnect');"
    ) == "2"


def test_legacy_overloads_also_skip_deleted_sources(pg):
    """Production still has the 5- and 6-argument rag_search; they must apply the rule too."""
    legacy = """
    CREATE FUNCTION public.rag_search(p_org_id uuid, p_query_embedding text, p_top_k int,
      p_source_id uuid DEFAULT NULL, p_document_id uuid DEFAULT NULL)
    RETURNS TABLE (chunk_id uuid, content text, source_id uuid, document_id uuid, chunk_index int,
      score float, source_title text, document_title text)
    LANGUAGE sql STABLE AS $$ SELECT NULL::uuid, NULL::text, NULL::uuid, NULL::uuid, 0, 0::float, 'stale'::text, NULL::text $$;
    CREATE FUNCTION public.rag_search(p_org_id uuid, p_query_embedding text, p_top_k int,
      p_source_id uuid DEFAULT NULL, p_document_id uuid DEFAULT NULL, p_environment text DEFAULT 'default')
    RETURNS TABLE (chunk_id uuid, content text, source_id uuid, document_id uuid, chunk_index int,
      score float, source_title text, document_title text)
    LANGUAGE sql STABLE AS $$ SELECT NULL::uuid, NULL::text, NULL::uuid, NULL::uuid, 0, 0::float, 'stale'::text, NULL::text $$;
    """
    pg.psql(legacy)
    pg.psql(MIGRATION.read_text())
    # Both legacy bodies now delegate to the 8-argument version.
    for sig in ("uuid,text,integer,uuid,uuid", "uuid,text,integer,uuid,uuid,text"):
        assert pg.value(
            f"SELECT prosrc LIKE '%p_department_id => NULL%' FROM pg_proc WHERE oid = 'public.rag_search({sig})'::regprocedure;"
        ) == "t", sig
        assert "stale" not in pg.value(f"SELECT prosrc FROM pg_proc WHERE oid = 'public.rag_search({sig})'::regprocedure;")
    keep = _source(pg, "keep")
    drop = _source(pg, "drop")
    pg.psql(f"UPDATE public.rag_sources SET deleted_at = now() WHERE id = '{drop}';")
    titles = pg.value(
        "SELECT string_agg(source_title, ',') FROM public.rag_search("
        f"p_org_id => '{ORG}'::uuid, p_query_embedding => '{VEC}', p_top_k => 50, p_source_id => NULL::uuid, "
        "p_document_id => NULL::uuid, p_environment => 'default', p_department_id => NULL::uuid, p_agent_id => NULL::uuid);"
    )
    assert titles == "keep" and keep


def test_migration_does_not_create_legacy_overloads(pg):
    pg.psql(MIGRATION.read_text())
    assert pg.value("SELECT count(*) FROM pg_proc WHERE proname = 'rag_search';") == "1"

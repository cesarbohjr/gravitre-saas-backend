"""Privilege hygiene migration (real PostgreSQL): no TRUNCATE, no client EXECUTE on definers."""
from __future__ import annotations

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

MIGRATION = MIGRATIONS / "20261013060000_privilege_hygiene.sql"

pytestmark = requires_pg

BOOTSTRAP_SQL = """
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
CREATE TABLE public.marketplace_assets (id uuid PRIMARY KEY, install_count int NOT NULL DEFAULT 0);
CREATE TABLE public.approvals (id uuid PRIMARY KEY);
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;
CREATE FUNCTION public.increment_marketplace_asset_counter(p_asset_id uuid, p_counter text)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v int; BEGIN
  UPDATE public.marketplace_assets SET install_count = install_count + 1 WHERE id = p_asset_id RETURNING install_count INTO v;
  RETURN v; END $$;
CREATE FUNCTION public.auth_org_accessible(target uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER AS $$ SELECT false $$;
CREATE FUNCTION public.handle_new_user() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER AS $$ BEGIN RETURN NEW; END $$;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO anon, authenticated;
INSERT INTO public.marketplace_assets VALUES ('11111111-1111-4111-8111-111111111111');
"""


def test_privilege_hygiene():
    with pg_cluster(BOOTSTRAP_SQL, MIGRATION.read_text()) as pg:
        for role in ("anon", "authenticated"):
            assert pg.value(f"SELECT has_table_privilege('{role}', 'public.approvals', 'TRUNCATE')") == "f"
            assert pg.value(f"SELECT has_table_privilege('{role}', 'public.approvals', 'SELECT')") == "t"
            r = pg.psql(
                f"SET ROLE {role}; SELECT public.increment_marketplace_asset_counter("
                "'11111111-1111-4111-8111-111111111111', 'install_count');",
                check=False,
            )
            assert r.returncode != 0 and "permission denied" in r.stderr, role
            assert pg.value(f"SELECT has_function_privilege('{role}', 'public.handle_new_user()', 'EXECUTE')") == "f"
            # Left alone on purpose: RLS policies call it.
            assert pg.value(f"SELECT has_function_privilege('{role}', 'public.auth_org_accessible(uuid)', 'EXECUTE')") == "t"
        r = pg.psql(
            "SET ROLE service_role; SELECT public.increment_marketplace_asset_counter("
            "'11111111-1111-4111-8111-111111111111', 'install_count');",
            check=False,
        )
        assert r.returncode == 0, r.stderr
        pg.psql(MIGRATION.read_text())  # idempotent

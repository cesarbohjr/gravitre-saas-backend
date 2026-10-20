"""Role contract for org settings and shared workspace tables (real PostgreSQL).

Applies ``20261013050000_settings_and_workspace_role_contract.sql`` unchanged on
tables shaped like production, with their member FOR ALL policies, and acts as
admin / member / viewer / outsider through SET ROLE authenticated.
"""
from __future__ import annotations

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

MIGRATION = MIGRATIONS / "20261013050000_settings_and_workspace_role_contract.sql"

ORG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ADMIN = "11111111-1111-4111-8111-111111111111"
MEMBER = "22222222-2222-4222-8222-222222222222"
VIEWER = "33333333-3333-4333-8333-333333333333"

pytestmark = requires_pg

PRED = "org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())"
TABLES = {
    "webhooks": "url text, events jsonb, status text, secret_hash text",
    "model_settings": "workspace_model text, allow_overrides boolean",
    "api_keys": "name text, status text, key_hash text",
    "connected_systems": "name text, status text, config jsonb",
    "workflows": "name text, status text, nodes jsonb",
    "council_sessions": "objective text, status text, final_decision jsonb",
}

BOOTSTRAP_SQL = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE SCHEMA auth;
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
GRANT USAGE ON SCHEMA public, auth TO anon, authenticated, service_role;
CREATE TABLE public.organization_members (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, user_id uuid NOT NULL, role text NOT NULL
);
ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;
CREATE POLICY om_self ON public.organization_members FOR SELECT USING (user_id = auth.uid());
GRANT SELECT ON public.organization_members TO authenticated;
""" + "".join(
    f"""
CREATE TABLE public.{t} (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, {cols});
ALTER TABLE public.{t} ENABLE ROW LEVEL SECURITY;
CREATE POLICY {t}_org_scope ON public.{t} FOR ALL USING ({PRED}) WITH CHECK ({PRED});
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON public.{t} TO anon, authenticated;
GRANT ALL ON public.{t} TO service_role;
INSERT INTO public.{t} (org_id) VALUES ('{ORG}');
"""
    for t, cols in TABLES.items()
) + f"""
INSERT INTO public.organization_members (org_id, user_id, role) VALUES
  ('{ORG}', '{ADMIN}', 'admin'), ('{ORG}', '{MEMBER}', 'member'), ('{ORG}', '{VIEWER}', 'viewer'),
  ('{OTHER}', '{MEMBER}', 'member');
"""


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(BOOTSTRAP_SQL, MIGRATION.read_text()) as server:
        yield server


def run_as(pg, user: str, sql: str):
    return pg.psql(
        "BEGIN; SET LOCAL ROLE authenticated; "
        f"SELECT set_config('request.jwt.claim.sub', '{user}', true); {sql}; ROLLBACK;",
        check=False,
    )


def ok(r) -> bool:
    return r.returncode == 0


def refused(r) -> bool:
    return r.returncode != 0 and ("Your role cannot change" in r.stderr or "permission denied" in r.stderr)


ADMIN_ONLY = ("webhooks", "model_settings", "api_keys")
NON_VIEWER = ("connected_systems", "workflows", "council_sessions")


@pytest.mark.parametrize("table", ADMIN_ONLY)
def test_org_settings_tables_are_admin_only(pg, table):
    assert ok(run_as(pg, ADMIN, f"UPDATE public.{table} SET org_id = org_id WHERE org_id = '{ORG}'"))
    assert ok(run_as(pg, ADMIN, f"INSERT INTO public.{table} (org_id) VALUES ('{ORG}')"))
    assert ok(run_as(pg, ADMIN, f"DELETE FROM public.{table} WHERE org_id = '{ORG}'"))
    for user in (MEMBER, VIEWER):
        assert refused(run_as(pg, user, f"UPDATE public.{table} SET org_id = org_id WHERE org_id = '{ORG}'")), (table, user)
        assert refused(run_as(pg, user, f"INSERT INTO public.{table} (org_id) VALUES ('{ORG}')")), (table, user)
        assert refused(run_as(pg, user, f"DELETE FROM public.{table} WHERE org_id = '{ORG}'")), (table, user)


@pytest.mark.parametrize("table", NON_VIEWER)
def test_workspace_tables_exclude_viewers(pg, table):
    for user in (ADMIN, MEMBER):
        assert ok(run_as(pg, user, f"INSERT INTO public.{table} (org_id) VALUES ('{ORG}')")), (table, user)
        assert ok(run_as(pg, user, f"DELETE FROM public.{table} WHERE org_id = '{ORG}'")), (table, user)
    assert refused(run_as(pg, VIEWER, f"INSERT INTO public.{table} (org_id) VALUES ('{ORG}')"))
    assert refused(run_as(pg, VIEWER, f"DELETE FROM public.{table} WHERE org_id = '{ORG}'"))
    assert refused(run_as(pg, VIEWER, f"UPDATE public.{table} SET org_id = org_id WHERE org_id = '{ORG}'"))


@pytest.mark.parametrize("table", list(TABLES))
def test_rows_cannot_move_to_another_org(pg, table):
    # MEMBER belongs to both orgs; moving a row is still refused.
    r = run_as(pg, ADMIN if table in ADMIN_ONLY else MEMBER, f"UPDATE public.{table} SET org_id = '{OTHER}' WHERE org_id = '{ORG}'")
    assert r.returncode != 0, table


@pytest.mark.parametrize("table", list(TABLES))
def test_reads_unchanged_and_anon_cannot_write(pg, table):
    r = run_as(pg, VIEWER, f"SELECT count(*) FROM public.{table}")
    assert ok(r) and r.stdout.strip().splitlines()[-1] == "1"
    anon = pg.psql(f"BEGIN; SET LOCAL ROLE anon; INSERT INTO public.{table} (org_id) VALUES ('{ORG}'); ROLLBACK;", check=False)
    assert anon.returncode != 0 and "permission denied" in anon.stderr


def test_service_role_unaffected(pg):
    r = pg.psql(
        "BEGIN; SET LOCAL ROLE service_role; "
        + "".join(f"INSERT INTO public.{t} (org_id) VALUES ('{ORG}'); " for t in TABLES)
        + "ROLLBACK;",
        check=False,
    )
    assert ok(r), r.stderr


def test_idempotent(pg):
    pg.psql(MIGRATION.read_text())
    assert pg.value("SELECT count(*) FROM pg_trigger WHERE tgname LIKE '%_role_contract';") == "6"

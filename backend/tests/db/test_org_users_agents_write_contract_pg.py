"""Field-level write contract for organizations, users and agents (real PostgreSQL).

Recreates the production table columns and member FOR ALL policies, applies
``20261013040000_org_users_agents_member_write_contract.sql`` unchanged, and acts
as owner / admin / member / viewer through SET ROLE authenticated with a JWT sub.
"""
from __future__ import annotations

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

MIGRATION = MIGRATIONS / "20261013040000_org_users_agents_member_write_contract.sql"

ORG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ADMIN = "11111111-1111-4111-8111-111111111111"
MEMBER = "22222222-2222-4222-8222-222222222222"
VIEWER = "33333333-3333-4333-8333-333333333333"
OTHER_ORG = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

pytestmark = requires_pg

PRED = "org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())"

BOOTSTRAP_SQL = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE SCHEMA auth;
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
GRANT USAGE ON SCHEMA public, auth TO anon, authenticated, service_role;
CREATE TABLE public.organizations (
  id uuid PRIMARY KEY, name text, created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now(),
  settings jsonb NOT NULL DEFAULT '{{}}', slug text, status text DEFAULT 'active', data_region text DEFAULT 'us', logo_url text
);
CREATE TABLE public.organization_members (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, user_id uuid NOT NULL, role text NOT NULL
);
CREATE TABLE public.users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, auth_user_id uuid, email text,
  full_name text, role text, status text DEFAULT 'active', created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(), external_id text, provisioned_via text, is_active boolean DEFAULT true,
  avatar_url text, job_title text, department text
);
CREATE TABLE public.agents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, name text, model text,
  systems jsonb, guardrails jsonb, config jsonb, created_by uuid, updated_at timestamptz DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agents ENABLE ROW LEVEL SECURITY;
CREATE POLICY om_self ON public.organization_members FOR SELECT USING (user_id = auth.uid());
CREATE POLICY organizations_org_scope ON public.organizations FOR ALL
  USING (id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()))
  WITH CHECK (id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()));
CREATE POLICY users_org_scope ON public.users FOR ALL USING ({PRED}) WITH CHECK ({PRED});
CREATE POLICY agents_org_scope ON public.agents FOR ALL USING ({PRED}) WITH CHECK ({PRED});

INSERT INTO public.organizations (id, name, settings) VALUES
  ('{ORG}', 'Acme', '{{"billing": {{"plan": "starter"}}, "isolated_conversation_test_org": false, "notificationPreferences": {{"emailEnabled": false}}}}'),
  ('{OTHER_ORG}', 'Other', '{{}}');
INSERT INTO public.organization_members (org_id, user_id, role) VALUES
  ('{ORG}', '{ADMIN}', 'admin'), ('{ORG}', '{MEMBER}', 'member'), ('{ORG}', '{VIEWER}', 'viewer');
INSERT INTO public.users (id, org_id, auth_user_id, email, full_name, role) VALUES
  ('aaaa0000-0000-4000-8000-000000000001', '{ORG}', '{ADMIN}', 'a@x.io', 'Ada', 'admin'),
  ('aaaa0000-0000-4000-8000-000000000002', '{ORG}', '{MEMBER}', 'm@x.io', 'Max', 'member'),
  ('aaaa0000-0000-4000-8000-000000000003', '{ORG}', '{VIEWER}', 'v@x.io', 'Vi', 'viewer');
INSERT INTO public.agents (id, org_id, name, created_by) VALUES
  ('cccc0000-0000-4000-8000-000000000001', '{ORG}', 'Ops', '{ADMIN}');
"""

MEMBER_ROW = "aaaa0000-0000-4000-8000-000000000002"
ADMIN_ROW = "aaaa0000-0000-4000-8000-000000000001"
AGENT = "cccc0000-0000-4000-8000-000000000001"


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(BOOTSTRAP_SQL, MIGRATION.read_text()) as server:
        yield server


def run(pg, user, sql):
    return pg.psql(
        "BEGIN; SET LOCAL ROLE authenticated; "
        f"SELECT set_config('request.jwt.claim.sub', '{user}', true); {sql}; ROLLBACK;",
        check=False,
    )


def ok(r) -> bool:
    return r.returncode == 0


def refused(r) -> bool:
    assert "permission denied for function" not in r.stderr, r.stderr
    return r.returncode != 0 and ("managed by Gravitre" in r.stderr or "owner or admin" in r.stderr
                                  or "permission denied" in r.stderr or "Viewers cannot" in r.stderr
                                  or "cannot change" in r.stderr)


# ------------------------------------------------------------ organizations


def test_member_cannot_rename_or_touch_settings(pg):
    assert refused(run(pg, MEMBER, f"UPDATE public.organizations SET name = 'Pwned' WHERE id = '{ORG}'"))
    assert refused(run(pg, MEMBER, f"UPDATE public.organizations SET settings = settings || '{{\"notificationPreferences\": {{}}}}' WHERE id = '{ORG}'"))


def test_admin_edits_allowed_fields(pg):
    assert ok(run(pg, ADMIN, f"UPDATE public.organizations SET name = 'Acme 2', slug = 'acme-2', logo_url = 'https://x/l.png' WHERE id = '{ORG}'"))
    assert ok(run(pg, ADMIN, f"UPDATE public.organizations SET settings = jsonb_set(settings, '{{notificationPreferences,emailEnabled}}', 'true') WHERE id = '{ORG}'"))


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE public.organizations SET status = 'suspended'",
        "UPDATE public.organizations SET data_region = 'eu'",
        "UPDATE public.organizations SET settings = jsonb_set(settings, '{billing,plan}', '\"enterprise\"')",
        "UPDATE public.organizations SET settings = settings || '{\"isolated_conversation_test_org\": true}'",
        "UPDATE public.organizations SET settings = settings || '{\"memoryEntityEmbeddings\": {\"enabled\": true}}'",
        "UPDATE public.organizations SET settings = '{}'",
    ],
)
def test_admin_cannot_change_gravitre_managed_fields(pg, sql):
    assert refused(run(pg, ADMIN, f"{sql} WHERE id = '{ORG}'"))


def test_nobody_inserts_or_deletes_orgs_through_the_api(pg):
    assert refused(run(pg, ADMIN, f"DELETE FROM public.organizations WHERE id = '{ORG}'"))
    assert refused(run(pg, ADMIN, "INSERT INTO public.organizations (id, name) VALUES (gen_random_uuid(), 'x')"))


# --------------------------------------------------------------------- users


def test_member_edits_own_profile_only(pg):
    assert ok(run(pg, MEMBER, f"UPDATE public.users SET full_name = 'Maxine', job_title = 'Ops' WHERE id = '{MEMBER_ROW}'"))
    assert refused(run(pg, MEMBER, f"UPDATE public.users SET role = 'owner' WHERE id = '{MEMBER_ROW}'"))
    assert refused(run(pg, MEMBER, f"UPDATE public.users SET status = 'inactive' WHERE id = '{ADMIN_ROW}'"))
    assert refused(run(pg, MEMBER, f"UPDATE public.users SET full_name = 'x' WHERE id = '{ADMIN_ROW}'"))


def test_member_cannot_delete_or_insert_users(pg):
    assert refused(run(pg, MEMBER, f"DELETE FROM public.users WHERE id = '{ADMIN_ROW}'"))
    assert refused(run(pg, MEMBER, f"INSERT INTO public.users (org_id, email) VALUES ('{ORG}', 'new@x.io')"))


def test_admin_manages_team_rows(pg):
    assert ok(run(pg, ADMIN, f"UPDATE public.users SET role = 'admin', status = 'active', full_name = 'M' WHERE id = '{MEMBER_ROW}'"))
    assert ok(run(pg, ADMIN, f"DELETE FROM public.users WHERE id = '{MEMBER_ROW}'"))


def test_identity_fields_are_never_writable(pg):
    for col, val in (("email", "'z@x.io'"), ("auth_user_id", f"'{VIEWER}'"), ("org_id", f"'{OTHER_ORG}'"), ("external_id", "'e'")):
        assert refused(run(pg, ADMIN, f"UPDATE public.users SET {col} = {val} WHERE id = '{MEMBER_ROW}'")), col


# -------------------------------------------------------------------- agents


def test_members_create_and_edit_agents(pg):
    assert ok(run(pg, MEMBER, f"INSERT INTO public.agents (org_id, name, created_by) VALUES ('{ORG}', 'Mine', '{MEMBER}')"))
    assert ok(run(pg, MEMBER, f"UPDATE public.agents SET name = 'Ops 2', systems = '[\"gmail\"]' WHERE id = '{AGENT}'"))


def test_viewers_cannot_write_agents(pg):
    assert refused(run(pg, VIEWER, f"UPDATE public.agents SET name = 'x' WHERE id = '{AGENT}'"))
    assert refused(run(pg, VIEWER, f"INSERT INTO public.agents (org_id, name) VALUES ('{ORG}', 'v')"))
    assert refused(run(pg, VIEWER, f"DELETE FROM public.agents WHERE id = '{AGENT}'"))


def test_agent_org_and_creator_are_fixed(pg):
    assert refused(run(pg, ADMIN, f"UPDATE public.agents SET created_by = '{MEMBER}' WHERE id = '{AGENT}'"))


# ------------------------------------------------------------- service role


def test_service_role_is_unaffected(pg):
    r = pg.psql(
        "BEGIN; SET LOCAL ROLE service_role; "
        f"UPDATE public.organizations SET settings = '{{}}', status = 'suspended' WHERE id = '{ORG}'; "
        f"UPDATE public.users SET email = 'svc@x.io' WHERE id = '{MEMBER_ROW}'; "
        "INSERT INTO public.organizations (id, name) VALUES (gen_random_uuid(), 'new'); ROLLBACK;",
        check=False,
    )
    assert r.returncode == 0, r.stderr


def test_idempotent(pg):
    pg.psql(MIGRATION.read_text())
    assert refused(run(pg, MEMBER, f"UPDATE public.organizations SET name = 'x' WHERE id = '{ORG}'"))

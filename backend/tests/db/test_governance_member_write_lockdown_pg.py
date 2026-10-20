"""Governance tables lose member writes; reads stay as they were (real PostgreSQL).

Builds the pre-migration policy shapes copied from the original migrations
(including the member FOR ALL policies and organization_members self insert /
self update), applies ``20261013010000_governance_tables_member_write_lockdown.sql``
unchanged, then acts as an `authenticated` member through SET ROLE with a JWT
subject, the way PostgREST does.

Release 1 gate: a member cannot approve their own queued write through the
database API, cannot add themselves to another org, and cannot raise their role.
"""
from __future__ import annotations

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

MIGRATION = MIGRATIONS / "20261013010000_governance_tables_member_write_lockdown.sql"

ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ORG_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
MEMBER = "11111111-1111-4111-8111-111111111111"
ADMIN = "22222222-2222-4222-8222-222222222222"
APPROVAL = "33333333-3333-4333-8333-333333333333"

pytestmark = requires_pg

MEMBER_PRED = "org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())"

BOOTSTRAP_SQL = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE SCHEMA auth;
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
GRANT USAGE ON SCHEMA public, auth TO anon, authenticated, service_role;

CREATE TABLE public.organizations (id uuid PRIMARY KEY, name text, settings jsonb NOT NULL DEFAULT '{{}}');
CREATE TABLE public.organization_members (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id),
  user_id uuid NOT NULL,
  role text NOT NULL DEFAULT 'member'
);
CREATE TABLE public.approvals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL, title text NOT NULL DEFAULT 't',
  status text NOT NULL DEFAULT 'pending', requested_by text, reviewed_by text
);
CREATE TABLE public.run_approvals (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, approver_id uuid);
CREATE TABLE public.workflow_runs (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, status text);
CREATE TABLE public.agent_identity_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL,
  trust_level text NOT NULL DEFAULT 'write_with_approval', approval_rule_overrides jsonb
);
CREATE TABLE public.agent_delegation_grants (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, delegated_permissions jsonb);
CREATE TABLE public.mcp_servers (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, server_url text, transport text);
CREATE TABLE public.mcp_tools (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, capability_tier text);
CREATE TABLE public.mcp_tool_executions (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, status text);
CREATE TABLE public.connectors (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, status text);
CREATE TABLE public.connector_secrets (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, secret text);

-- Supabase's default: authenticated may write every public table; RLS decides.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
DO $$ DECLARE t text; BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;

-- Pre-migration policies, as in the original migrations.
CREATE POLICY organizations_org_scope ON public.organizations FOR ALL
  USING (id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()))
  WITH CHECK (id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()));
CREATE POLICY organization_members_self_select ON public.organization_members FOR SELECT USING (user_id = auth.uid());
CREATE POLICY organization_members_self_insert ON public.organization_members FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY organization_members_self_update ON public.organization_members FOR UPDATE
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY approvals_org_scope ON public.approvals FOR ALL USING ({MEMBER_PRED}) WITH CHECK ({MEMBER_PRED});
CREATE POLICY run_approvals_org ON public.run_approvals FOR ALL USING ({MEMBER_PRED});
CREATE POLICY workflow_runs_org ON public.workflow_runs FOR ALL USING ({MEMBER_PRED});
CREATE POLICY agent_identity_records_org_scope ON public.agent_identity_records FOR ALL USING ({MEMBER_PRED});
CREATE POLICY agent_delegation_grants_org_scope ON public.agent_delegation_grants FOR ALL USING ({MEMBER_PRED});
CREATE POLICY mcp_servers_org_isolation ON public.mcp_servers FOR ALL USING ({MEMBER_PRED});
CREATE POLICY mcp_tools_org_isolation ON public.mcp_tools FOR ALL USING ({MEMBER_PRED});
CREATE POLICY mcp_tool_executions_org_isolation ON public.mcp_tool_executions FOR ALL USING ({MEMBER_PRED});
CREATE POLICY connectors_org_scope ON public.connectors FOR ALL USING ({MEMBER_PRED}) WITH CHECK ({MEMBER_PRED});
CREATE POLICY connector_secrets_org ON public.connector_secrets FOR ALL USING ({MEMBER_PRED});

INSERT INTO public.organizations (id, name, settings) VALUES
  ('{ORG_A}', 'A', '{{"approvalRules": {{"customerEmailApproval": true}}, "theme": "dark"}}'),
  ('{ORG_B}', 'B', '{{}}');
INSERT INTO public.organization_members (org_id, user_id, role) VALUES
  ('{ORG_A}', '{MEMBER}', 'member'), ('{ORG_A}', '{ADMIN}', 'admin');
INSERT INTO public.approvals (id, org_id, requested_by) VALUES ('{APPROVAL}', '{ORG_A}', '{MEMBER}');
INSERT INTO public.agent_identity_records (org_id) VALUES ('{ORG_A}');
INSERT INTO public.connectors (org_id, status) VALUES ('{ORG_A}', 'connected');
INSERT INTO public.connector_secrets (org_id, secret) VALUES ('{ORG_A}', 'ciphertext');
INSERT INTO public.mcp_servers (org_id, server_url, transport) VALUES ('{ORG_A}', 'https://x', 'streamable_http');
"""


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(BOOTSTRAP_SQL, MIGRATION.read_text()) as server:
        yield server


def as_user(user: str, sql: str) -> str:
    return (
        "BEGIN; SET LOCAL ROLE authenticated; "
        f"SELECT set_config('request.jwt.claim.sub', '{user}', true); {sql}; COMMIT;"
    )


def run_as(pg, user: str, sql: str):
    return pg.psql(as_user(user, sql), check=False)


def denied(result) -> bool:
    return result.returncode != 0 and (
        "permission denied" in result.stderr or "row-level security" in result.stderr
    )


# ------------------------------------------------------------------ membership


def test_member_cannot_add_themselves_to_another_org(pg):
    r = run_as(pg, MEMBER, f"INSERT INTO public.organization_members (org_id, user_id, role) VALUES ('{ORG_B}', '{MEMBER}', 'owner')")
    assert denied(r), r.stderr
    assert pg.value(f"SELECT count(*) FROM public.organization_members WHERE org_id = '{ORG_B}'") == "0"


def test_member_cannot_raise_their_own_role(pg):
    r = run_as(pg, MEMBER, f"UPDATE public.organization_members SET role = 'owner' WHERE user_id = '{MEMBER}'")
    assert denied(r), r.stderr
    assert pg.value(f"SELECT role FROM public.organization_members WHERE user_id = '{MEMBER}'") == "member"


def test_member_still_reads_own_membership(pg):
    r = run_as(pg, MEMBER, "SELECT count(*) FROM public.organization_members")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().splitlines()[-1] == "1"


# ------------------------------------------------------------------- approvals


def test_member_cannot_approve_their_own_queued_write(pg):
    r = run_as(pg, MEMBER, f"UPDATE public.approvals SET status = 'approved', reviewed_by = '{MEMBER}' WHERE id = '{APPROVAL}'")
    assert denied(r), r.stderr
    assert pg.value(f"SELECT status FROM public.approvals WHERE id = '{APPROVAL}'") == "pending"


def test_admin_cannot_approve_through_the_database_either(pg):
    """Approval decisions go through the backend (admin check, binding, audit)."""
    r = run_as(pg, ADMIN, f"UPDATE public.approvals SET status = 'approved' WHERE id = '{APPROVAL}'")
    assert denied(r), r.stderr


def test_member_cannot_insert_or_delete_approvals(pg):
    assert denied(run_as(pg, MEMBER, f"INSERT INTO public.approvals (org_id, status) VALUES ('{ORG_A}', 'approved')"))
    assert denied(run_as(pg, MEMBER, f"DELETE FROM public.approvals WHERE id = '{APPROVAL}'"))


def test_member_reads_approvals_in_their_org_only(pg):
    pg.psql(f"INSERT INTO public.approvals (org_id) VALUES ('{ORG_B}')")
    r = run_as(pg, MEMBER, "SELECT count(*) FROM public.approvals")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().splitlines()[-1] == "1"


# --------------------------------------------------------- other governance rows


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE public.agent_identity_records SET trust_level = 'autonomous', approval_rule_overrides = '{\"write\":\"auto_run\"}'",
        f"INSERT INTO public.agent_delegation_grants (org_id, delegated_permissions) VALUES ('{ORG_A}', '{{\"elevated_trust_level\":\"autonomous\"}}')",
        f"INSERT INTO public.mcp_servers (org_id, server_url, transport) VALUES ('{ORG_A}', 'bash -c id', 'stdio')",
        "UPDATE public.mcp_tools SET capability_tier = 'read'",
        "UPDATE public.mcp_tool_executions SET status = 'completed'",
        "UPDATE public.connectors SET status = 'connected'",
        "UPDATE public.workflow_runs SET status = 'completed'",
        f"INSERT INTO public.run_approvals (org_id, approver_id) VALUES ('{ORG_A}', '{MEMBER}')",
    ],
)
def test_member_cannot_write_governance_tables(pg, sql):
    assert denied(run_as(pg, MEMBER, sql))


def test_member_reads_are_unchanged_for_governance_tables(pg):
    for table in ("agent_identity_records", "mcp_servers", "connectors"):
        r = run_as(pg, MEMBER, f"SELECT count(*) FROM public.{table}")
        assert r.returncode == 0, (table, r.stderr)
        assert r.stdout.strip().splitlines()[-1] == "1", table


def test_connector_secrets_are_backend_only(pg):
    assert denied(run_as(pg, MEMBER, "SELECT secret FROM public.connector_secrets"))
    assert denied(run_as(pg, ADMIN, "SELECT secret FROM public.connector_secrets"))


def test_anon_has_no_access(pg):
    r = pg.psql("BEGIN; SET LOCAL ROLE anon; SELECT count(*) FROM public.approvals; COMMIT;", check=False)
    assert denied(r), r.stderr


def test_service_role_still_writes(pg):
    r = pg.psql(
        "BEGIN; SET LOCAL ROLE service_role; "
        f"UPDATE public.approvals SET status = 'approved' WHERE id = '{APPROVAL}'; "
        f"INSERT INTO public.organization_members (org_id, user_id, role) VALUES ('{ORG_B}', '{ADMIN}', 'owner'); "
        "ROLLBACK;",
        check=False,
    )
    assert r.returncode == 0, r.stderr


# ------------------------------------------------------- organizations settings


def test_member_cannot_change_approval_rules(pg):
    r = run_as(
        pg,
        MEMBER,
        f"UPDATE public.organizations SET settings = jsonb_set(settings, '{{approvalRules,customerEmailApproval}}', 'false') WHERE id = '{ORG_A}'",
    )
    assert r.returncode != 0 and "approval rules" in r.stderr, r.stderr
    assert pg.value(f"SELECT settings->'approvalRules'->>'customerEmailApproval' FROM public.organizations WHERE id = '{ORG_A}'") == "true"


def test_member_can_still_change_other_settings(pg):
    r = run_as(pg, MEMBER, f"UPDATE public.organizations SET settings = jsonb_set(settings, '{{theme}}', '\"light\"') WHERE id = '{ORG_A}'")
    assert r.returncode == 0, r.stderr
    assert pg.value(f"SELECT settings->>'theme' FROM public.organizations WHERE id = '{ORG_A}'") == "light"


def test_admin_can_change_approval_rules(pg):
    r = run_as(
        pg,
        ADMIN,
        f"UPDATE public.organizations SET settings = jsonb_set(settings, '{{approvalRules,customerEmailApproval}}', 'false') WHERE id = '{ORG_A}'",
    )
    assert r.returncode == 0, r.stderr
    pg.psql(f"UPDATE public.organizations SET settings = jsonb_set(settings, '{{approvalRules,customerEmailApproval}}', 'true') WHERE id = '{ORG_A}'")


def test_migration_is_idempotent(pg):
    pg.psql(MIGRATION.read_text())
    assert denied(run_as(pg, MEMBER, f"UPDATE public.approvals SET status = 'approved' WHERE id = '{APPROVAL}'"))
    r = run_as(pg, MEMBER, "SELECT count(*) FROM public.approvals")
    assert r.returncode == 0, r.stderr

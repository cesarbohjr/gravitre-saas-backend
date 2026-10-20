"""Emergency: members cannot join other orgs or raise their role (real PostgreSQL).

Recreates the production policies on organization_members (self select, self
insert, self update, all keyed only on user_id = auth.uid()) and Supabase's
default write grants, shows the hole is open, applies
``20261013005000_emergency_membership_write_lockdown.sql`` unchanged, and checks
it is closed for anon and members while reads and service-role writes still work.
"""
from __future__ import annotations

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

MIGRATION = MIGRATIONS / "20261013005000_emergency_membership_write_lockdown.sql"

ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ORG_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
MEMBER = "11111111-1111-4111-8111-111111111111"
OUTSIDER = "22222222-2222-4222-8222-222222222222"

pytestmark = requires_pg

BOOTSTRAP_SQL = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE SCHEMA auth;
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
GRANT USAGE ON SCHEMA public, auth TO anon, authenticated, service_role;
CREATE TABLE public.organizations (id uuid PRIMARY KEY);
CREATE TABLE public.organization_members (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id),
  user_id uuid NOT NULL,
  role text NOT NULL DEFAULT 'member'
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.organization_members TO anon, authenticated;
GRANT ALL ON public.organization_members TO service_role;
ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;
CREATE POLICY "organization_members_self_select" ON public.organization_members FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "organization_members_self_insert" ON public.organization_members FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "organization_members_self_update" ON public.organization_members FOR UPDATE
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
INSERT INTO public.organizations VALUES ('{ORG_A}'), ('{ORG_B}');
INSERT INTO public.organization_members (org_id, user_id, role) VALUES ('{ORG_A}', '{MEMBER}', 'member');
"""


def _as(user: str, sql: str) -> str:
    return (
        "BEGIN; SET LOCAL ROLE authenticated; "
        f"SELECT set_config('request.jwt.claim.sub', '{user}', true); {sql}; COMMIT;"
    )


def _denied(result) -> bool:
    return result.returncode != 0 and (
        "permission denied" in result.stderr or "row-level security" in result.stderr
    )


JOIN_B = f"INSERT INTO public.organization_members (org_id, user_id, role) VALUES ('{ORG_B}', '{{u}}', 'owner')"
PROMOTE = f"UPDATE public.organization_members SET role = 'owner' WHERE user_id = '{MEMBER}'"


def test_hole_is_open_before_and_closed_after():
    with pg_cluster(BOOTSTRAP_SQL) as pg:
        # Before: an outsider joins org B as owner; a member promotes themselves.
        assert pg.psql(_as(OUTSIDER, JOIN_B.format(u=OUTSIDER)), check=False).returncode == 0
        assert pg.psql(_as(MEMBER, PROMOTE), check=False).returncode == 0
        assert pg.value(f"SELECT role FROM public.organization_members WHERE user_id = '{MEMBER}'") == "owner"

        pg.psql(f"DELETE FROM public.organization_members WHERE org_id = '{ORG_B}'; "
                f"UPDATE public.organization_members SET role = 'member' WHERE user_id = '{MEMBER}';")
        pg.psql(MIGRATION.read_text())

        assert _denied(pg.psql(_as(OUTSIDER, JOIN_B.format(u=OUTSIDER)), check=False))
        assert _denied(pg.psql(_as(MEMBER, JOIN_B.format(u=MEMBER)), check=False))
        assert _denied(pg.psql(_as(MEMBER, PROMOTE), check=False))
        assert _denied(pg.psql(_as(MEMBER, f"DELETE FROM public.organization_members WHERE user_id = '{MEMBER}'"), check=False))
        assert pg.value(f"SELECT count(*) FROM public.organization_members WHERE org_id = '{ORG_B}'") == "0"
        assert pg.value(f"SELECT role FROM public.organization_members WHERE user_id = '{MEMBER}'") == "member"

        # Anonymous callers get nothing at all.
        anon = pg.psql("BEGIN; SET LOCAL ROLE anon; SELECT count(*) FROM public.organization_members; COMMIT;", check=False)
        assert _denied(anon)

        # Members still read their own memberships.
        own = pg.psql(_as(MEMBER, "SELECT count(*) FROM public.organization_members"), check=False)
        assert own.returncode == 0 and own.stdout.strip().splitlines()[-1] == "1"

        # The backend (service role) still manages memberships.
        svc = pg.psql(
            "BEGIN; SET LOCAL ROLE service_role; "
            f"INSERT INTO public.organization_members (org_id, user_id, role) VALUES ('{ORG_B}', '{OUTSIDER}', 'admin'); "
            "ROLLBACK;",
            check=False,
        )
        assert svc.returncode == 0, svc.stderr

        # Only the SELECT policy remains, and re-applying is harmless.
        pg.psql(MIGRATION.read_text())
        assert pg.value(
            "SELECT string_agg(policyname || ':' || cmd, ',') FROM pg_policies WHERE tablename = 'organization_members';"
        ) == "organization_members_self_select:SELECT"

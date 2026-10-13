"""connector_action_availability: members read their org's rows and cannot write (real PostgreSQL).

Builds the table and FOR ALL member policy exactly as
``20261007090000_outcome_pack_ledger_claims.sql`` leaves them, shows a member
can mark a vendor unavailable for their org, applies
``20261013081000_connector_action_availability_member_read_only.sql`` unchanged,
and checks member and anon writes are refused while member reads and service
role writes still work.
"""
from __future__ import annotations

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

MIGRATION = MIGRATIONS / "20261013081000_connector_action_availability_member_read_only.sql"

ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ORG_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
MEMBER = "11111111-1111-4111-8111-111111111111"

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
CREATE TABLE public.organization_members (org_id uuid NOT NULL, user_id uuid NOT NULL);
GRANT SELECT ON public.organization_members TO authenticated;
CREATE TABLE public.connector_action_availability (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  vendor text NOT NULL,
  action text NOT NULL DEFAULT '*',
  state text NOT NULL,
  reason text,
  observed_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz,
  UNIQUE (org_id, vendor, action)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.connector_action_availability TO anon, authenticated;
GRANT ALL ON public.connector_action_availability TO service_role;
ALTER TABLE public.connector_action_availability ENABLE ROW LEVEL SECURITY;
CREATE POLICY connector_action_availability_org_scope
  ON public.connector_action_availability FOR ALL TO authenticated
  USING (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = (SELECT auth.uid())))
  WITH CHECK (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = (SELECT auth.uid())));
INSERT INTO public.organizations VALUES ('{ORG_A}'), ('{ORG_B}');
INSERT INTO public.organization_members VALUES ('{ORG_A}', '{MEMBER}');
INSERT INTO public.connector_action_availability (org_id, vendor, state) VALUES
  ('{ORG_A}', 'hubspot', 'rate_limited'), ('{ORG_B}', 'hubspot', 'rate_limited');
"""


def _as_member(sql: str) -> str:
    return (
        "BEGIN; SET LOCAL ROLE authenticated; "
        f"SELECT set_config('request.jwt.claim.sub', '{MEMBER}', true); {sql}; COMMIT;"
    )


def _denied(result) -> bool:
    return result.returncode != 0 and (
        "permission denied" in result.stderr or "row-level security" in result.stderr
    )


BLOCK_SALESFORCE = (
    f"INSERT INTO public.connector_action_availability (org_id, vendor, state) VALUES ('{ORG_A}', 'salesforce', 'plan_limit')"
)
UNBLOCK_HUBSPOT = f"UPDATE public.connector_action_availability SET state = 'available' WHERE org_id = '{ORG_A}'"


def test_member_writes_open_before_and_closed_after():
    with pg_cluster(BOOTSTRAP_SQL) as pg:
        # Before: a member can block a vendor for the whole org.
        assert pg.psql(_as_member(BLOCK_SALESFORCE), check=False).returncode == 0
        pg.psql(f"DELETE FROM public.connector_action_availability WHERE vendor = 'salesforce';")

        pg.psql(MIGRATION.read_text())

        assert _denied(pg.psql(_as_member(BLOCK_SALESFORCE), check=False))
        # Updates and deletes see no rows to change (no write policy), so they
        # succeed as no-ops; the row below must be untouched.
        pg.psql(_as_member(UNBLOCK_HUBSPOT), check=False)
        pg.psql(_as_member("DELETE FROM public.connector_action_availability"), check=False)
        assert pg.value(f"SELECT state FROM public.connector_action_availability WHERE org_id = '{ORG_A}'") == "rate_limited"

        # Members still read their own org's rows, and only those.
        own = pg.psql(_as_member("SELECT count(*) FROM public.connector_action_availability"), check=False)
        assert own.returncode == 0 and own.stdout.strip().splitlines()[-1] == "1", own.stdout

        # Anonymous callers get nothing.
        anon = pg.psql("BEGIN; SET LOCAL ROLE anon; SELECT count(*) FROM public.connector_action_availability; COMMIT;", check=False)
        assert _denied(anon) or anon.stdout.strip().splitlines()[-1] == "0", anon.stdout

        # The backend (service role) still records refusals.
        svc = pg.psql(
            "BEGIN; SET LOCAL ROLE service_role; " + BLOCK_SALESFORCE + "; ROLLBACK;",
            check=False,
        )
        assert svc.returncode == 0, svc.stderr

        # Re-applying is harmless and leaves only the SELECT policy.
        pg.psql(MIGRATION.read_text())
        assert pg.value(
            "SELECT string_agg(policyname || ':' || cmd, ',') FROM pg_policies "
            "WHERE tablename = 'connector_action_availability';"
        ) == "connector_action_availability_org_member_read:SELECT"

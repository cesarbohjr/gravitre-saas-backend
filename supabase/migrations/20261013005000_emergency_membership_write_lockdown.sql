-- EMERGENCY: org members cannot add themselves to orgs or change their own role.
--
-- organization_members_self_insert (FOR INSERT WITH CHECK user_id = auth.uid()) let
-- any signed-in user, holding the public anon key and their own session token,
-- insert a membership for themselves into ANY org with ANY role.
-- organization_members_self_update let a member change their own role (e.g. to
-- owner). `authenticated` also held INSERT/UPDATE grants, confirmed in production.
-- Every other member-scoped RLS policy and the backend's admin checks read this
-- table, so both holes undermine all of them.
--
-- Fix: drop every non-SELECT policy on organization_members and revoke member
-- writes. Members keep reading their own memberships (organization_members_self_select
-- is untouched). Memberships are written only by the backend (service role, which
-- bypasses RLS) and by the SECURITY DEFINER signup trigger, neither affected. The
-- web app's team role change now goes through the backend's admin-checked
-- PATCH /api/org/members/{id} (same release).
--
-- Preflight (read-only):
--   select policyname, cmd, qual, with_check from pg_policies
--    where schemaname = 'public' and tablename = 'organization_members';
--   select grantee, privilege_type from information_schema.role_table_grants
--    where table_schema = 'public' and table_name = 'organization_members'
--      and grantee in ('anon', 'authenticated');
-- Postcheck: the same two queries show only SELECT policies and only SELECT for
-- authenticated (nothing for anon).
--
-- Rollback (re-opens the hole; only if a legitimate client turns out to need it):
--   GRANT INSERT, UPDATE ON public.organization_members TO authenticated;
--   and the two CREATE POLICY statements from 20260424_gravitre_frontend_contract_schema.sql.
--
-- 20261013010000_governance_tables_member_write_lockdown.sql repeats this for
-- organization_members (idempotent) and extends it to the other governance tables.

DO $$
DECLARE
  p record;
BEGIN
  IF to_regclass('public.organization_members') IS NULL THEN
    RETURN;
  END IF;
  ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;
  FOR p IN
    SELECT policyname FROM pg_policies
     WHERE schemaname = 'public' AND tablename = 'organization_members' AND cmd <> 'SELECT'
  LOOP
    EXECUTE format('DROP POLICY %I ON public.organization_members', p.policyname);
  END LOOP;
  REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.organization_members FROM anon, authenticated;
  REVOKE ALL ON public.organization_members FROM anon;
  GRANT SELECT ON public.organization_members TO authenticated;
END;
$$;

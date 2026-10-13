-- connector_action_availability: members may read their org's rows, never write them.
--
-- 20261007090000_outcome_pack_ledger_claims.sql created this table with one
-- FOR ALL policy for `authenticated`, so any org member holding the public anon
-- key and their own session token could insert or update rows through PostgREST.
-- The objective planner and capability fallback read this table to decide which
-- provider to use, so a member could mark a vendor as plan_limit / auth_expired
-- (and the planner would stop using it) or as available (and it would retry a
-- blocked one), for the whole org.
--
-- Every legitimate writer is the backend (record_unavailable in
-- app/services/capability_availability.py, through the service role client,
-- which bypasses RLS). Nothing in the web app touches the table. This matches
-- capability_usage_events: members SELECT, only the service role writes.
--
-- Applied to production on 2026-10-13 (version 20261013081000 is recorded in
-- supabase_migrations.schema_migrations); this file mirrors what ran there.
-- With RLS on and no write policy, member inserts, updates and deletes are
-- refused even though table grants are unchanged.
--
-- Check (read only):
--   select policyname, cmd, roles from pg_policies
--    where schemaname = 'public' and tablename = 'connector_action_availability';
-- Expected: only connector_action_availability_org_member_read, SELECT, authenticated.
--
-- Rollback (re-opens member writes):
--   DROP POLICY connector_action_availability_org_member_read ON public.connector_action_availability;
--   and the CREATE POLICY connector_action_availability_org_scope statement from
--   20261007090000_outcome_pack_ledger_claims.sql.

DO $$
DECLARE
  p record;
BEGIN
  IF to_regclass('public.connector_action_availability') IS NULL THEN
    RETURN;
  END IF;

  ALTER TABLE public.connector_action_availability ENABLE ROW LEVEL SECURITY;

  FOR p IN
    SELECT policyname FROM pg_policies
     WHERE schemaname = 'public' AND tablename = 'connector_action_availability'
       AND policyname <> 'connector_action_availability_org_member_read'
  LOOP
    EXECUTE format('DROP POLICY %I ON public.connector_action_availability', p.policyname);
  END LOOP;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
     WHERE schemaname = 'public' AND tablename = 'connector_action_availability'
       AND policyname = 'connector_action_availability_org_member_read'
  ) THEN
    CREATE POLICY connector_action_availability_org_member_read
      ON public.connector_action_availability
      FOR SELECT
      TO authenticated
      USING (
        org_id IN (
          SELECT om.org_id
          FROM public.organization_members om
          WHERE om.user_id = (SELECT auth.uid())
        )
      );
  END IF;

END;
$$;

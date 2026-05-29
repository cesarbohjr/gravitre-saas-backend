-- Row Level Security for guardrail_events.
--
-- The table (20260530000000_guardrail_events.sql) has org_id but no RLS, so a
-- client role could read another tenant's guardrail/failover events. Enable RLS
-- and restrict reads to members of the owning org.
--
-- NOTE: the spec template referenced a `profiles` table, which does not exist in
-- this schema. Tenant membership here lives in organization_members (this is the
-- same pattern used by the model_calls RLS policy), so the policy uses that.
-- Writes come from the service role (which bypasses RLS), so no INSERT policy is
-- needed for the application path.

ALTER TABLE public.guardrail_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation" ON public.guardrail_events;
CREATE POLICY "tenant_isolation"
  ON public.guardrail_events
  FOR SELECT
  USING (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid()
    )
  );

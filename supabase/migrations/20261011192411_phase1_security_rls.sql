-- Phase 1 security: RLS gaps, multi-org membership predicate, webhook dedupe, MCP approval single-use.
--
-- What this does (idempotent, non-destructive; no data is rewritten or dropped):
--   1. agent_custom_voices (20260808085000) and billing_topup_events (20260808204958)
--      had no RLS and kept Supabase's default anon/authenticated grants, so PostgREST
--      exposed them. RLS is enabled, org members may SELECT their org's rows, anon
--      loses all privileges, and writes stay with the service role (the backend).
--   2. work_objects / work_object_events (20260904174500), agent_memories
--      (20260629120000) and agent_memory_history (20260903120000) scoped rows with
--      `org_id = (SELECT org_id ... WHERE user_id = auth.uid() LIMIT 1)`, which picks
--      an arbitrary org for multi-org users. They now use the membership predicate
--      used by recent migrations: org_id IN (SELECT org_id FROM organization_members
--      WHERE user_id = auth.uid()).
--   3. webhook_event_receipts: one row per (org_id, provider, event_id) so provider
--      retries of HubSpot/Salesforce/Segment/PagerDuty webhooks do not start
--      duplicate workflow runs. RLS on with no policies: service role only.
--   4. approvals.consumed_at: MCP write approvals are claimed once
--      (UPDATE ... WHERE status = 'approved' AND consumed_at IS NULL). The backend
--      fails closed for MCP writes until this column exists.
--
-- Supabase applies each migration file in its own transaction, so no explicit
-- BEGIN/COMMIT (consistent with the other migrations in this directory).
--
-- Preflight (read-only, run before applying):
--   SELECT relname, relrowsecurity FROM pg_class
--    WHERE relnamespace = 'public'::regnamespace
--      AND relname IN ('agent_custom_voices','billing_topup_events','work_objects',
--                      'work_object_events','agent_memories','agent_memory_history','approvals');
--   SELECT tablename, policyname, qual FROM pg_policies
--    WHERE schemaname = 'public'
--      AND tablename IN ('agent_custom_voices','billing_topup_events','work_objects',
--                        'work_object_events','agent_memories','agent_memory_history');
--   -- Users with more than one org are the ones the LIMIT 1 policies mis-scoped:
--   SELECT user_id, count(*) FROM public.organization_members GROUP BY 1 HAVING count(*) > 1;
--   -- Confirm no browser client reads agent_custom_voices / billing_topup_events
--   -- with the anon key (the backend uses the service role, which bypasses RLS).
--
-- Rollback (manual; restores the previous exposure, so only if this breaks prod):
--   ALTER TABLE public.agent_custom_voices DISABLE ROW LEVEL SECURITY;
--   DROP POLICY IF EXISTS "agent_custom_voices_org_select" ON public.agent_custom_voices;
--   ALTER TABLE public.billing_topup_events DISABLE ROW LEVEL SECURITY;
--   DROP POLICY IF EXISTS "billing_topup_events_org_select" ON public.billing_topup_events;
--   GRANT ALL ON public.agent_custom_voices, public.billing_topup_events TO anon, authenticated;
--   -- Re-create the previous LIMIT 1 bodies from 20260904174500 / 20260629120000 /
--   -- 20260903120000 for the four org policies if required.
--   DROP TABLE IF EXISTS public.webhook_event_receipts;   -- dedupe turns off; backend tolerates it
--   ALTER TABLE public.approvals DROP COLUMN IF EXISTS consumed_at;  -- MCP writes then fail closed

-- -----------------------------------------------------------------------------
-- 1) agent_custom_voices / billing_topup_events
-- -----------------------------------------------------------------------------
ALTER TABLE public.agent_custom_voices ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "agent_custom_voices_org_select" ON public.agent_custom_voices;
CREATE POLICY "agent_custom_voices_org_select"
  ON public.agent_custom_voices FOR SELECT
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

REVOKE ALL ON public.agent_custom_voices FROM anon;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.agent_custom_voices FROM authenticated;

ALTER TABLE public.billing_topup_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "billing_topup_events_org_select" ON public.billing_topup_events;
CREATE POLICY "billing_topup_events_org_select"
  ON public.billing_topup_events FOR SELECT
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

REVOKE ALL ON public.billing_topup_events FROM anon;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.billing_topup_events FROM authenticated;

-- -----------------------------------------------------------------------------
-- 2) Multi-org membership predicate (replaces `= (... LIMIT 1)`)
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "work_objects_org" ON public.work_objects;
CREATE POLICY "work_objects_org"
  ON public.work_objects FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

DROP POLICY IF EXISTS "work_object_events_org" ON public.work_object_events;
CREATE POLICY "work_object_events_org"
  ON public.work_object_events FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

DROP POLICY IF EXISTS "agent_memories_org" ON public.agent_memories;
CREATE POLICY "agent_memories_org"
  ON public.agent_memories FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

DROP POLICY IF EXISTS "agent_memory_history_org" ON public.agent_memory_history;
CREATE POLICY "agent_memory_history_org"
  ON public.agent_memory_history FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

-- -----------------------------------------------------------------------------
-- 3) Webhook event receipts (provider retry dedupe)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.webhook_event_receipts (
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  provider text NOT NULL,
  event_id text NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, provider, event_id)
);

CREATE INDEX IF NOT EXISTS idx_webhook_event_receipts_received_at
  ON public.webhook_event_receipts (received_at);

COMMENT ON TABLE public.webhook_event_receipts IS
  'Inbound webhook idempotency: one row per (org, provider, provider event id[:workflow id]). Service role only.';

ALTER TABLE public.webhook_event_receipts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.webhook_event_receipts FROM anon, authenticated;
GRANT ALL ON public.webhook_event_receipts TO service_role;

-- -----------------------------------------------------------------------------
-- 4) MCP approvals are single-use
-- -----------------------------------------------------------------------------
ALTER TABLE public.approvals
  ADD COLUMN IF NOT EXISTS consumed_at timestamptz;

COMMENT ON COLUMN public.approvals.consumed_at IS
  'Set when an approval authorising a single action (MCP write) has been used; reuse is rejected.';

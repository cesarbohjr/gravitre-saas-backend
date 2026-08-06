-- Phase 0 (perf-reliability-db-audit-2026-08-05 F1):
-- Enable RLS on 8 public tables flagged rls_disabled_in_public.
-- Reuses the proven org-membership pattern from
-- 20260617120000_enable_rls_flagged_public_tables.sql.
-- Backend service_role bypasses RLS; policies protect PostgREST/client access.

-- ---------------------------------------------------------------------------
-- Org-scoped intelligence / interrupt tables
-- ---------------------------------------------------------------------------

ALTER TABLE public.agent_execution_interrupts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "agent_execution_interrupts_org_scope" ON public.agent_execution_interrupts;
CREATE POLICY "agent_execution_interrupts_org_scope"
  ON public.agent_execution_interrupts FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

ALTER TABLE public.intelligence_outcome_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "intelligence_outcome_events_org_scope" ON public.intelligence_outcome_events;
CREATE POLICY "intelligence_outcome_events_org_scope"
  ON public.intelligence_outcome_events FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

ALTER TABLE public.intelligence_learning_signals ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "intelligence_learning_signals_org_scope" ON public.intelligence_learning_signals;
CREATE POLICY "intelligence_learning_signals_org_scope"
  ON public.intelligence_learning_signals FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

ALTER TABLE public.strategy_performance_records ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "strategy_performance_records_org_scope" ON public.strategy_performance_records;
CREATE POLICY "strategy_performance_records_org_scope"
  ON public.strategy_performance_records FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

ALTER TABLE public.domain_segment_learning_state ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "domain_segment_learning_state_org_scope" ON public.domain_segment_learning_state;
CREATE POLICY "domain_segment_learning_state_org_scope"
  ON public.domain_segment_learning_state FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

ALTER TABLE public.domain_optimization_recommendations ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "domain_optimization_recommendations_org_scope"
  ON public.domain_optimization_recommendations;
CREATE POLICY "domain_optimization_recommendations_org_scope"
  ON public.domain_optimization_recommendations FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

ALTER TABLE public.test_credential_org_allowlist ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "test_credential_org_allowlist_org_scope"
  ON public.test_credential_org_allowlist;
CREATE POLICY "test_credential_org_allowlist_org_scope"
  ON public.test_credential_org_allowlist FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

-- Global allowlist of restricted test user ids — no org_id. Deny client roles;
-- service_role continues to bypass RLS for internal guards.
ALTER TABLE public.restricted_test_user_ids ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "restricted_test_user_ids_deny_clients"
  ON public.restricted_test_user_ids;
CREATE POLICY "restricted_test_user_ids_deny_clients"
  ON public.restricted_test_user_ids FOR ALL
  USING (false)
  WITH CHECK (false);

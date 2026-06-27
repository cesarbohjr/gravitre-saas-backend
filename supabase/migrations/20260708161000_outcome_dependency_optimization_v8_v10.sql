-- v8 Outcome-Linked Learning, v10 Optimization Suggestions, v4 candidate type extensions

-- ---------------------------------------------------------------------------
-- v8: agent_action_outcomes (correlational attribution, not RL)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.agent_action_outcomes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  agent_id uuid,
  workflow_run_id uuid,
  action_type text NOT NULL,
  target_entity_type text NOT NULL,
  target_entity_id text NOT NULL,
  action_taken_at timestamptz NOT NULL,
  metric_name text NOT NULL,
  metric_value_before double precision,
  metric_value_after double precision,
  attribution_window_days integer NOT NULL DEFAULT 14,
  measured_at timestamptz,
  confidence_note text NOT NULL DEFAULT
    'correlational only; other factors may have contributed to this metric change',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_action_outcomes_entity
  ON public.agent_action_outcomes (org_id, target_entity_type, target_entity_id);

CREATE INDEX IF NOT EXISTS idx_agent_action_outcomes_agent_measured
  ON public.agent_action_outcomes (org_id, agent_id, measured_at);

CREATE INDEX IF NOT EXISTS idx_agent_action_outcomes_pending_measurement
  ON public.agent_action_outcomes (org_id, action_taken_at)
  WHERE measured_at IS NULL;

ALTER TABLE public.agent_action_outcomes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS agent_action_outcomes_org_scope ON public.agent_action_outcomes;
CREATE POLICY agent_action_outcomes_org_scope
  ON public.agent_action_outcomes FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

COMMENT ON TABLE public.agent_action_outcomes IS
  'v8 outcome-linked learning: baseline + delayed measurement; correlational only.';

-- ---------------------------------------------------------------------------
-- v10: optimization_suggestions (human-gated; no auto_apply state)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.optimization_suggestions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  target_entity_type text NOT NULL,
  target_entity_id text NOT NULL,
  suggestion_type text NOT NULL,
  evidence jsonb NOT NULL,
  suggested_action text NOT NULL,
  estimated_impact text,
  status text NOT NULL DEFAULT 'pending_review'
    CHECK (status IN ('pending_review', 'applied', 'dismissed')),
  reviewed_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  reviewed_at timestamptz,
  applied_change_summary text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_optimization_suggestions_org_status
  ON public.optimization_suggestions (org_id, status, created_at DESC);

ALTER TABLE public.optimization_suggestions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS optimization_suggestions_org_scope ON public.optimization_suggestions;
CREATE POLICY optimization_suggestions_org_scope
  ON public.optimization_suggestions FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

COMMENT ON TABLE public.optimization_suggestions IS
  'v10 human-gated optimization suggestions; detection never writes production config.';

-- ---------------------------------------------------------------------------
-- Extend v4 memory promotion candidate types (v8 outcome_pattern, v11 decision_pattern)
-- ---------------------------------------------------------------------------
ALTER TABLE public.memory_promotion_candidates
  DROP CONSTRAINT IF EXISTS memory_promotion_candidates_candidate_type_check;

ALTER TABLE public.memory_promotion_candidates
  ADD CONSTRAINT memory_promotion_candidates_candidate_type_check
  CHECK (candidate_type IN (
    'glossary',
    'workflow_pattern',
    'successful_response',
    'outcome_pattern',
    'decision_pattern'
  ));

-- Wave D1: org-local domain-segment adaptive learning state (first-class storage)

CREATE TABLE IF NOT EXISTS public.domain_segment_learning_state (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  segment_key text NOT NULL,
  industry text,
  department text,
  subdomain text,
  task_type text,
  source_weight_deltas jsonb NOT NULL DEFAULT '{}'::jsonb,
  assignment_boost_deltas jsonb NOT NULL DEFAULT '{}'::jsonb,
  memory_category_boost_deltas jsonb NOT NULL DEFAULT '{}'::jsonb,
  connector_priority_deltas jsonb NOT NULL DEFAULT '{}'::jsonb,
  adaptive_weight_delta numeric(6, 4) NOT NULL DEFAULT 1.0,
  outcome_multiplier numeric(6, 4) NOT NULL DEFAULT 1.0,
  meta_learning_delta numeric(6, 4) NOT NULL DEFAULT 1.0,
  freshness_aggregate numeric(6, 4) NOT NULL DEFAULT 1.0,
  graph_weight_delta numeric(6, 4) NOT NULL DEFAULT 1.0,
  confidence_threshold_delta numeric(6, 4) NOT NULL DEFAULT 0.0,
  sample_count integer NOT NULL DEFAULT 0,
  positive_count integer NOT NULL DEFAULT 0,
  negative_count integer NOT NULL DEFAULT 0,
  noise_score numeric(6, 4) NOT NULL DEFAULT 0.0,
  learning_confidence text NOT NULL DEFAULT 'insufficient_data',
  meta_learning_state jsonb NOT NULL DEFAULT '{}'::jsonb,
  optimization_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
  last_updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT domain_segment_learning_state_org_segment UNIQUE (org_id, segment_key)
);

CREATE INDEX IF NOT EXISTS idx_domain_segment_learning_org_segment
  ON public.domain_segment_learning_state (org_id, segment_key);

CREATE INDEX IF NOT EXISTS idx_domain_segment_learning_org_updated
  ON public.domain_segment_learning_state (org_id, last_updated_at DESC);

COMMENT ON TABLE public.domain_segment_learning_state IS
  'Org-local adaptive learning weights per domain segment. No cross-tenant learning.';

COMMENT ON COLUMN public.domain_segment_learning_state.meta_learning_state IS
  'Reserved for Wave D3 MetaLearningService strategy outcomes per segment.';

COMMENT ON COLUMN public.domain_segment_learning_state.optimization_snapshot IS
  'Reserved for Wave D5 DomainOptimizationEngine metric snapshots.';

-- Wave D5 advisory recommendations (human-gated; no auto-execution)
CREATE TABLE IF NOT EXISTS public.domain_optimization_recommendations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  segment_key text NOT NULL,
  recommendation_type text NOT NULL,
  title text NOT NULL,
  description text,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'pending_review',
  advisory_only boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT domain_optimization_recommendations_status CHECK (
    status IN ('pending_review', 'applied', 'dismissed')
  )
);

CREATE INDEX IF NOT EXISTS idx_domain_optimization_recs_org_status
  ON public.domain_optimization_recommendations (org_id, status, created_at DESC);

COMMENT ON TABLE public.domain_optimization_recommendations IS
  'Advisory-only domain optimization recommendations. Humans remain in control.';

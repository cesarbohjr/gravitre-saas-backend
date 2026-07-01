-- Unified intelligence outcome events (extends v8/v7 — does not replace agent_action_outcomes)
CREATE TABLE IF NOT EXISTS public.intelligence_outcome_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  outcome_event text NOT NULL,
  entity_type text,
  entity_id text,
  recommendation_id text,
  prediction_id text,
  workflow_id text,
  workflow_run_id text,
  agent_id uuid,
  connector_id uuid,
  department text,
  task_type text,
  model_name text,
  confidence_score double precision,
  before_value double precision,
  after_value double precision,
  measured_at timestamptz,
  measurement_status text DEFAULT 'recorded',
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_intelligence_outcome_events_org_created
  ON public.intelligence_outcome_events (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_intelligence_outcome_events_org_event
  ON public.intelligence_outcome_events (org_id, outcome_event);

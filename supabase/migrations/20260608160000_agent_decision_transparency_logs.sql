-- STA-112: EU AI Act agent decision transparency logs

CREATE TABLE IF NOT EXISTS public.agent_decision_transparency_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  decision_source text NOT NULL,
  operator_id uuid REFERENCES public.operators(id) ON DELETE SET NULL,
  operator_session_id uuid,
  action_plan_id uuid,
  workflow_run_id uuid REFERENCES public.workflow_runs(id) ON DELETE SET NULL,
  actor_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  input_context jsonb NOT NULL DEFAULT '{}'::jsonb,
  model_info jsonb NOT NULL DEFAULT '{}'::jsonb,
  tools_invoked jsonb NOT NULL DEFAULT '[]'::jsonb,
  human_override jsonb,
  outcome jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'in_progress'
    CHECK (status IN ('in_progress', 'completed', 'failed', 'pending_approval', 'blocked', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_transparency_logs_org_created
  ON public.agent_decision_transparency_logs (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_transparency_logs_run
  ON public.agent_decision_transparency_logs (org_id, workflow_run_id)
  WHERE workflow_run_id IS NOT NULL;

ALTER TABLE public.agent_decision_transparency_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "transparency_logs_org" ON public.agent_decision_transparency_logs;
CREATE POLICY "transparency_logs_org"
  ON public.agent_decision_transparency_logs FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

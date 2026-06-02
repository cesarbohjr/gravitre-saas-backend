-- STA-17: Cross-agent handoff data bus

CREATE TABLE IF NOT EXISTS public.agent_handoffs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  workflow_run_id uuid REFERENCES public.workflow_runs(id) ON DELETE SET NULL,
  workflow_step_id text,
  from_agent_id uuid NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
  to_agent_id uuid NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
  briefing jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_output jsonb,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'completed', 'failed')),
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_agent_handoffs_org_created
  ON public.agent_handoffs (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_handoffs_run
  ON public.agent_handoffs (workflow_run_id);
CREATE INDEX IF NOT EXISTS idx_agent_handoffs_to_agent
  ON public.agent_handoffs (to_agent_id, created_at DESC);

ALTER TABLE public.agent_handoffs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "agent_handoffs_tenant" ON public.agent_handoffs;
CREATE POLICY "agent_handoffs_tenant"
  ON public.agent_handoffs
  FOR SELECT
  USING (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.agent_handoffs IS
  'Cross-agent handoff records with briefing payload (contact, deal, decision, artifacts).';
COMMENT ON COLUMN public.agent_handoffs.briefing IS
  'Handoff briefing: { contact?, deal?, decision?, artifacts[] }';

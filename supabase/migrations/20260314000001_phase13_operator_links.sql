-- Phase 13: Operator links (agent handoffs)
-- Authority: docs/phase-11/WORKFLOWS_ORCHESTRATOR_UI.md

CREATE TABLE public.operator_links (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  environment text NOT NULL,
  from_operator_id uuid NOT NULL REFERENCES public.operators(id) ON DELETE CASCADE,
  to_operator_id uuid NOT NULL REFERENCES public.operators(id) ON DELETE CASCADE,
  link_type text NOT NULL DEFAULT 'handoff',
  task text,
  notes text,
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_operator_links_org_id ON public.operator_links(org_id);
CREATE INDEX idx_operator_links_from_operator ON public.operator_links(from_operator_id);
CREATE INDEX idx_operator_links_to_operator ON public.operator_links(to_operator_id);
CREATE INDEX idx_operator_links_env ON public.operator_links(environment);

ALTER TABLE public.operator_links ENABLE ROW LEVEL SECURITY;

CREATE POLICY "operator_links_org"
  ON public.operator_links FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

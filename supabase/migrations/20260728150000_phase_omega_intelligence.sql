-- Phase Omega: research monitors + consensus deliberation history + graph type docs

CREATE TABLE IF NOT EXISTS public.research_monitors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  topic TEXT NOT NULL,
  check_interval_hours INTEGER DEFAULT 24,
  last_checked_at TIMESTAMPTZ,
  last_findings JSONB DEFAULT '{}'::jsonb,
  enabled BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(org_id, topic)
);

ALTER TABLE public.research_monitors ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS research_monitors_isolation ON public.research_monitors;
CREATE POLICY research_monitors_isolation
  ON public.research_monitors FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  );

CREATE TABLE IF NOT EXISTS public.intelligence_consensus_deliberations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  recommendation_summary TEXT,
  confidence DOUBLE PRECISION,
  vote_breakdown JSONB DEFAULT '{}'::jsonb,
  minority_opinions JSONB DEFAULT '[]'::jsonb,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_consensus_deliberations_org_created
  ON public.intelligence_consensus_deliberations (org_id, created_at DESC);

ALTER TABLE public.intelligence_consensus_deliberations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS intelligence_consensus_deliberations_org_scope
  ON public.intelligence_consensus_deliberations;
CREATE POLICY intelligence_consensus_deliberations_org_scope
  ON public.intelligence_consensus_deliberations FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.org_entity_relationships IS
  'v6 entity graph. Supported entity types include glossary_term, department, agent, '
  'workflow_run, customer, lead, deal, campaign, support_ticket, invoice, project, '
  'employee, prospect, contact, meeting, contract, vendor, task, objective, kpi. '
  'Supported relationship types include associated-department, referenced-by-agent, '
  'co-occurs-with, tracked-by, observed-in, belongs-to, influenced-by, reports_to, '
  'blocked_by, contributes_to, impacts, references.';

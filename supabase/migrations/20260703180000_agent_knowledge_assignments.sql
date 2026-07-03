-- Agent knowledge source assignments (Drive folders, SharePoint, Confluence, CRM scopes, etc.)

CREATE TABLE IF NOT EXISTS public.agent_knowledge_assignments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  agent_id uuid NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
  source_type text NOT NULL,
  source_id text NOT NULL,
  label text NOT NULL,
  include_rules jsonb NOT NULL DEFAULT '[]'::jsonb,
  exclude_rules jsonb NOT NULL DEFAULT '[]'::jsonb,
  sync_schedule text,
  owner_user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  confidence_score numeric(5, 4) DEFAULT 0.75,
  last_synced_at timestamptz,
  freshness_status text NOT NULL DEFAULT 'unknown',
  enabled boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT agent_knowledge_assignments_unique UNIQUE (org_id, agent_id, source_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_knowledge_assignments_org_agent
  ON public.agent_knowledge_assignments (org_id, agent_id);

DROP TRIGGER IF EXISTS agent_knowledge_assignments_set_updated_at ON public.agent_knowledge_assignments;
CREATE TRIGGER agent_knowledge_assignments_set_updated_at
  BEFORE UPDATE ON public.agent_knowledge_assignments
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.agent_knowledge_assignments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "agent_knowledge_assignments_org" ON public.agent_knowledge_assignments;
CREATE POLICY "agent_knowledge_assignments_org"
  ON public.agent_knowledge_assignments FOR ALL
  USING (
    org_id = (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1
    )
  );

COMMENT ON TABLE public.agent_knowledge_assignments IS
  'Runtime knowledge source bindings per agent — folders, sites, channels, knowledge packs.';

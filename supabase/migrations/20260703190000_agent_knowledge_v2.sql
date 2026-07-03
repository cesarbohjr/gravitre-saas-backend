-- Agent knowledge v2: extended assignments, reference-first storage, sync linkage

ALTER TABLE public.agent_knowledge_assignments
  ADD COLUMN IF NOT EXISTS connector_id uuid REFERENCES public.connectors(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS workspace_id uuid,
  ADD COLUMN IF NOT EXISTS external_source_url text,
  ADD COLUMN IF NOT EXISTS owning_department text,
  ADD COLUMN IF NOT EXISTS read_scope jsonb NOT NULL DEFAULT '["read"]'::jsonb,
  ADD COLUMN IF NOT EXISTS write_scope jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS learn_scope jsonb NOT NULL DEFAULT '["read","summarize"]'::jsonb,
  ADD COLUMN IF NOT EXISTS sync_enabled boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS sync_frequency text NOT NULL DEFAULT 'daily',
  ADD COLUMN IF NOT EXISTS tags_required jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS tags_excluded jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS freshness_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS permission_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS provenance_required boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS last_verified_at timestamptz,
  ADD COLUMN IF NOT EXISTS created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_agent_knowledge_assignments_connector
  ON public.agent_knowledge_assignments (org_id, connector_id)
  WHERE connector_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.agent_knowledge_references (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  agent_id uuid NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
  assignment_id uuid REFERENCES public.agent_knowledge_assignments(id) ON DELETE SET NULL,
  source_system text NOT NULL,
  connector_id uuid REFERENCES public.connectors(id) ON DELETE SET NULL,
  external_object_id text NOT NULL,
  external_url text,
  source_title text NOT NULL,
  source_type text NOT NULL,
  source_section text,
  source_updated_at timestamptz,
  last_synced_at timestamptz,
  last_verified_at timestamptz,
  confidence_score numeric(5, 4) DEFAULT 0.75,
  freshness_score numeric(5, 4) DEFAULT 0.75,
  permission_scope jsonb NOT NULL DEFAULT '{}'::jsonb,
  provenance_chain jsonb NOT NULL DEFAULT '[]'::jsonb,
  memory_type text NOT NULL DEFAULT 'reference',
  memory_summary text NOT NULL,
  embedding_reference text,
  graph_entity_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  reference_only boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT agent_knowledge_references_unique UNIQUE (org_id, agent_id, source_system, external_object_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_knowledge_references_org_agent
  ON public.agent_knowledge_references (org_id, agent_id);

DROP TRIGGER IF EXISTS agent_knowledge_references_set_updated_at ON public.agent_knowledge_references;
CREATE TRIGGER agent_knowledge_references_set_updated_at
  BEFORE UPDATE ON public.agent_knowledge_references
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.agent_knowledge_references ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "agent_knowledge_references_org" ON public.agent_knowledge_references;
CREATE POLICY "agent_knowledge_references_org"
  ON public.agent_knowledge_references FOR ALL
  USING (
    org_id = (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1
    )
  );

COMMENT ON TABLE public.agent_knowledge_references IS
  'Reference-first knowledge rows per agent — summaries/metadata only, no raw document payloads.';

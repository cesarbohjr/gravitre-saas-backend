-- Part 1 items 4–5: shared department memory + standing investigators setting.

-- ---------------------------------------------------------------------------
-- 4. Shared department memory on agent_memories
-- ---------------------------------------------------------------------------
ALTER TABLE public.agent_memories
  ADD COLUMN IF NOT EXISTS department_id uuid REFERENCES public.departments(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_agent_memories_org_department
  ON public.agent_memories (org_id, department_id)
  WHERE department_id IS NOT NULL;

COMMENT ON COLUMN public.agent_memories.department_id IS
  'Nullable department scope; when set, memories are RECALLable by any agent in the same department.';

-- Recursive department sub-agents: umbrella → children
ALTER TABLE public.agents
  ADD COLUMN IF NOT EXISTS parent_agent_id uuid REFERENCES public.agents(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_agents_org_parent
  ON public.agents (org_id, parent_agent_id)
  WHERE parent_agent_id IS NOT NULL;

COMMENT ON COLUMN public.agents.parent_agent_id IS
  'Umbrella/parent agent for recursive department sub-agents; null for top-level agents.';

-- Department-scoped vector search (shared across agents in the same department)
CREATE OR REPLACE FUNCTION public.agent_memory_search_by_department(
  p_org_id uuid,
  p_department_id uuid,
  p_query_embedding text,
  p_top_k int,
  p_category text DEFAULT NULL
)
RETURNS TABLE (
  memory_id uuid,
  content text,
  category text,
  provenance text,
  confidence numeric,
  usage_count int,
  editable boolean,
  agent_id uuid,
  department_id uuid,
  score float,
  created_at timestamptz
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    m.id AS memory_id,
    m.content,
    m.category,
    m.provenance,
    m.confidence,
    m.usage_count,
    m.editable,
    m.agent_id,
    m.department_id,
    (1 - (m.embedding <=> (p_query_embedding::vector(1536))))::float AS score,
    m.created_at
  FROM public.agent_memories m
  WHERE m.org_id = p_org_id
    AND m.department_id = p_department_id
    AND m.embedding IS NOT NULL
    AND (p_category IS NULL OR m.category = p_category)
    AND COALESCE(m.is_active, true) = true
  ORDER BY m.embedding <=> (p_query_embedding::vector(1536))
  LIMIT p_top_k;
$$;

-- ---------------------------------------------------------------------------
-- 5. Standing unprompted investigators (org admin setting, default ON)
-- ---------------------------------------------------------------------------
ALTER TABLE public.org_intelligence_engine_settings
  ADD COLUMN IF NOT EXISTS standing_investigators_enabled boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN public.org_intelligence_engine_settings.standing_investigators_enabled IS
  'When true (default), standing investigators run read-scoped advisory scans and notify admins. Explicit off disables.';

CREATE TABLE IF NOT EXISTS public.standing_investigator_findings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  finding_type text NOT NULL,
  title text NOT NULL,
  body text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  advisory_only boolean NOT NULL DEFAULT true,
  status text NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'acknowledged', 'dismissed')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_standing_investigator_findings_org
  ON public.standing_investigator_findings (org_id, created_at DESC);

ALTER TABLE public.standing_investigator_findings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS standing_investigator_findings_org ON public.standing_investigator_findings;
CREATE POLICY standing_investigator_findings_org
  ON public.standing_investigator_findings FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

COMMENT ON TABLE public.standing_investigator_findings IS
  'Advisory-only standing investigator findings; never auto-execute writes.';

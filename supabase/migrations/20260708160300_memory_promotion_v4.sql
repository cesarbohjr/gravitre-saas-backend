-- v4: Agent Memory Layer — promotion candidates, audit trail, memory lifecycle

ALTER TABLE public.agent_memories
  ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS expires_at timestamptz,
  ADD COLUMN IF NOT EXISTS last_retrieved_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_agent_memories_active
  ON public.agent_memories (org_id, agent_id, is_active)
  WHERE is_active IS TRUE;

COMMENT ON COLUMN public.agent_memories.is_active IS
  'Soft-delete / rollback flag; inactive memories are excluded from retrieval.';
COMMENT ON COLUMN public.agent_memories.expires_at IS
  'TTL for auto-promoted memories (v4); NULL means no fixed expiration.';
COMMENT ON COLUMN public.agent_memories.last_retrieved_at IS
  'Updated when memory is surfaced via agent_memory_search (v4 decay).';

CREATE TABLE IF NOT EXISTS public.memory_promotion_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  source_table text NOT NULL,
  source_id uuid,
  candidate_type text NOT NULL
    CHECK (candidate_type IN ('glossary', 'workflow_pattern', 'successful_response')),
  content text NOT NULL,
  memory_category text NOT NULL DEFAULT 'fact'
    CHECK (memory_category IN ('fact', 'preference', 'pattern', 'rule')),
  status text NOT NULL DEFAULT 'candidate'
    CHECK (status IN (
      'candidate', 'auto_promoted', 'pending_approval', 'approved',
      'rejected', 'written', 'expired', 'rolled_back'
    )),
  frequency integer NOT NULL DEFAULT 0,
  department_count integer NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  memory_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  rejection_reason text,
  content_fingerprint text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_promotion_candidates_source
  ON public.memory_promotion_candidates (org_id, source_table, source_id)
  WHERE source_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_promotion_candidates_fingerprint
  ON public.memory_promotion_candidates (org_id, content_fingerprint);

CREATE INDEX IF NOT EXISTS idx_memory_promotion_candidates_org_status
  ON public.memory_promotion_candidates (org_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.agent_memory_promotion_audit (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  memory_id uuid REFERENCES public.agent_memories(id) ON DELETE SET NULL,
  candidate_id uuid REFERENCES public.memory_promotion_candidates(id) ON DELETE SET NULL,
  source_table text NOT NULL,
  source_id uuid,
  promotion_path text NOT NULL CHECK (promotion_path IN ('auto', 'manual_approval')),
  decision_reasoning text NOT NULL,
  threshold_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
  decided_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  decided_at timestamptz NOT NULL DEFAULT now(),
  status_at_decision text NOT NULL,
  action text NOT NULL DEFAULT 'promote'
    CHECK (action IN ('promote', 'reject', 'rollback', 'expire'))
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_promotion_audit_org
  ON public.agent_memory_promotion_audit (org_id, decided_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_memory_promotion_audit_memory
  ON public.agent_memory_promotion_audit (memory_id);

CREATE INDEX IF NOT EXISTS idx_agent_memory_promotion_audit_auto
  ON public.agent_memory_promotion_audit (org_id, promotion_path, decided_at DESC)
  WHERE promotion_path = 'auto';

ALTER TABLE public.memory_promotion_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_memory_promotion_audit ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS memory_promotion_candidates_isolation ON public.memory_promotion_candidates;
CREATE POLICY memory_promotion_candidates_isolation
  ON public.memory_promotion_candidates FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

DROP POLICY IF EXISTS agent_memory_promotion_audit_isolation ON public.agent_memory_promotion_audit;
CREATE POLICY agent_memory_promotion_audit_isolation
  ON public.agent_memory_promotion_audit FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

-- Exclude inactive / expired memories from retrieval
CREATE OR REPLACE FUNCTION public.agent_memory_search(
  p_org_id uuid,
  p_agent_id uuid,
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
    (1 - (m.embedding <=> (p_query_embedding::vector(1536))))::float AS score,
    m.created_at
  FROM public.agent_memories m
  WHERE m.org_id = p_org_id
    AND m.agent_id = p_agent_id
    AND m.embedding IS NOT NULL
    AND m.is_active IS TRUE
    AND (m.expires_at IS NULL OR m.expires_at > now())
    AND (p_category IS NULL OR m.category = p_category)
  ORDER BY m.embedding <=> (p_query_embedding::vector(1536))
  LIMIT p_top_k;
$$;

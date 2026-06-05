-- STA-49: Per-agent vector memory store and search

CREATE TABLE IF NOT EXISTS public.agent_memories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  agent_id uuid NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
  content text NOT NULL,
  category text NOT NULL DEFAULT 'fact' CHECK (category IN ('fact', 'preference', 'pattern', 'rule')),
  provenance text,
  confidence numeric(5, 2) NOT NULL DEFAULT 100,
  usage_count integer NOT NULL DEFAULT 0,
  editable boolean NOT NULL DEFAULT true,
  embedding vector(1536),
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_memories_org_agent
  ON public.agent_memories (org_id, agent_id);

CREATE INDEX IF NOT EXISTS idx_agent_memories_category
  ON public.agent_memories (org_id, agent_id, category);

CREATE INDEX IF NOT EXISTS idx_agent_memories_hnsw
  ON public.agent_memories
  USING hnsw (embedding vector_cosine_ops)
  WHERE embedding IS NOT NULL;

DROP TRIGGER IF EXISTS agent_memories_set_updated_at ON public.agent_memories;
CREATE TRIGGER agent_memories_set_updated_at
  BEFORE UPDATE ON public.agent_memories
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.agent_memories ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "agent_memories_org" ON public.agent_memories;
CREATE POLICY "agent_memories_org"
  ON public.agent_memories FOR ALL
  USING (
    org_id = (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1
    )
  );

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
    AND (p_category IS NULL OR m.category = p_category)
  ORDER BY m.embedding <=> (p_query_embedding::vector(1536))
  LIMIT p_top_k;
$$;

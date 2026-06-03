-- STA-20: Department-scoped RAG sources and retrieval filtering

ALTER TABLE public.rag_sources
  ADD COLUMN IF NOT EXISTS department_id uuid REFERENCES public.departments(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS agent_id uuid REFERENCES public.agents(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_rag_sources_org_department
  ON public.rag_sources(org_id, department_id)
  WHERE department_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_rag_sources_org_agent
  ON public.rag_sources(org_id, agent_id)
  WHERE agent_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.rag_search(
  p_org_id uuid,
  p_query_embedding text,
  p_top_k int,
  p_source_id uuid DEFAULT NULL,
  p_document_id uuid DEFAULT NULL,
  p_environment text DEFAULT 'default',
  p_department_id uuid DEFAULT NULL,
  p_agent_id uuid DEFAULT NULL
)
RETURNS TABLE (
  chunk_id uuid,
  content text,
  source_id uuid,
  document_id uuid,
  chunk_index int,
  score float,
  source_title text,
  document_title text
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    c.id AS chunk_id,
    c.content,
    c.source_id,
    c.document_id,
    c.chunk_index,
    (1 - (e.embedding <=> (p_query_embedding::vector(1536))))::float AS score,
    s.title AS source_title,
    d.title AS document_title
  FROM public.rag_embeddings e
  JOIN public.rag_chunks c ON c.id = e.chunk_id
  JOIN public.rag_documents d ON d.id = c.document_id
  JOIN public.rag_sources s ON s.id = c.source_id
  WHERE e.org_id = p_org_id
    AND d.is_active IS TRUE
    AND e.environment = p_environment
    AND c.environment = p_environment
    AND d.environment = p_environment
    AND s.environment = p_environment
    AND (p_source_id IS NULL OR c.source_id = p_source_id)
    AND (p_document_id IS NULL OR c.document_id = p_document_id)
    AND (
      p_department_id IS NULL
      OR s.department_id IS NULL
      OR s.department_id = p_department_id
    )
    AND (
      p_agent_id IS NULL
      OR s.agent_id IS NULL
      OR s.agent_id = p_agent_id
    )
  ORDER BY e.embedding <=> (p_query_embedding::vector(1536))
  LIMIT p_top_k;
$$;

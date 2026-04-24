-- DC-00: RAG document versioning to prevent partial ingestion states
-- Adds is_active + archived_at and replaces unique constraint with partial unique index

ALTER TABLE public.rag_documents
  ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;

ALTER TABLE public.rag_documents
  ADD COLUMN IF NOT EXISTS archived_at timestamptz;

ALTER TABLE public.rag_documents
  DROP CONSTRAINT IF EXISTS rag_documents_source_id_external_id_key;

CREATE UNIQUE INDEX IF NOT EXISTS idx_rag_documents_active_external
  ON public.rag_documents (source_id, external_id)
  WHERE is_active IS TRUE AND external_id IS NOT NULL;

-- Ensure retrieval uses active documents only
CREATE OR REPLACE FUNCTION public.rag_search(
  p_org_id uuid,
  p_query_embedding text,
  p_top_k int,
  p_source_id uuid DEFAULT NULL,
  p_document_id uuid DEFAULT NULL
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
    AND (p_source_id IS NULL OR c.source_id = p_source_id)
    AND (p_document_id IS NULL OR c.document_id = p_document_id)
  ORDER BY e.embedding <=> (p_query_embedding::vector(1536))
  LIMIT p_top_k;
$$;

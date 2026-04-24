-- BE-10: RAG read-only baseline — sources, documents, chunks, embeddings, retrieval logs
-- Authority: docs/phase-1/BE-10_RAG_READ_ONLY_PLAN.md
-- Requires: pgvector (SA-00), organizations (BE-00)

-- rag_sources: registered sources (metadata only); org-scoped
CREATE TABLE public.rag_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  title text NOT NULL,
  type text NOT NULL,
  metadata jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_rag_sources_org_id ON public.rag_sources(org_id);
CREATE INDEX idx_rag_sources_org_id_type ON public.rag_sources(org_id, type);

-- rag_documents: document-level metadata; idempotency via (source_id, external_id)
CREATE TABLE public.rag_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  source_id uuid NOT NULL REFERENCES public.rag_sources(id) ON DELETE CASCADE,
  external_id text,
  title text,
  metadata jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_id, external_id)
);

CREATE INDEX idx_rag_documents_org_id ON public.rag_documents(org_id);
CREATE INDEX idx_rag_documents_source_id ON public.rag_documents(source_id);

-- rag_chunks: text chunks; org_id denormalized for RLS
CREATE TABLE public.rag_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES public.rag_documents(id) ON DELETE CASCADE,
  source_id uuid NOT NULL REFERENCES public.rag_sources(id) ON DELETE CASCADE,
  content text NOT NULL,
  chunk_index int NOT NULL,
  metadata jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_rag_chunks_org_id ON public.rag_chunks(org_id);
CREATE INDEX idx_rag_chunks_document_id ON public.rag_chunks(document_id);
CREATE INDEX idx_rag_chunks_source_id ON public.rag_chunks(source_id);

-- rag_embeddings: one vector per chunk; dimension 1536 (OpenAI text-embedding-3-small)
CREATE TABLE public.rag_embeddings (
  chunk_id uuid PRIMARY KEY REFERENCES public.rag_chunks(id) ON DELETE CASCADE,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  embedding vector(1536) NOT NULL,
  model_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_rag_embeddings_org_id ON public.rag_embeddings(org_id);
CREATE INDEX idx_rag_embeddings_hnsw ON public.rag_embeddings
  USING hnsw (embedding vector_cosine_ops);

-- rag_retrieval_logs: minimal audit; no query text or PII
CREATE TABLE public.rag_retrieval_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  query_id text NOT NULL,
  result_count int NOT NULL,
  latency_ms int,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_rag_retrieval_logs_org_created ON public.rag_retrieval_logs(org_id, created_at);

-- RLS: org-scoped; backend uses service role (bypasses RLS) and filters by org_id in app
ALTER TABLE public.rag_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rag_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rag_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rag_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rag_retrieval_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "rag_sources_org"
  ON public.rag_sources FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "rag_documents_org"
  ON public.rag_documents FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "rag_chunks_org"
  ON public.rag_chunks FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "rag_embeddings_org"
  ON public.rag_embeddings FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "rag_retrieval_logs_org"
  ON public.rag_retrieval_logs FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

-- BE-10: Vector search function (cosine distance); called by backend with org_id from auth
-- query_embedding: vector as text e.g. '[0.1,0.2,...]'; top_k capped by caller
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
    AND (p_source_id IS NULL OR c.source_id = p_source_id)
    AND (p_document_id IS NULL OR c.document_id = p_document_id)
  ORDER BY e.embedding <=> (p_query_embedding::vector(1536))
  LIMIT p_top_k;
$$;

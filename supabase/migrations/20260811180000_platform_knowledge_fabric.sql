-- Platform knowledge fabric: shared expert packs, structurally separate from org-scoped rag_*.
-- No customer org_id on shared rows. RLS: authenticated read of published packs; writes service-role only.

-- Extend department assignable resource types
ALTER TABLE public.department_resource_assignments
  DROP CONSTRAINT IF EXISTS department_resource_assignments_resource_type_check;

ALTER TABLE public.department_resource_assignments
  ADD CONSTRAINT department_resource_assignments_resource_type_check
  CHECK (resource_type IN ('workflow', 'agent', 'council', 'knowledge_pack'));

CREATE TABLE IF NOT EXISTS public.knowledge_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id text NOT NULL UNIQUE,
  publisher text NOT NULL,
  url text NOT NULL,
  source_type text NOT NULL,
  department text NOT NULL,
  industry text,
  topics text[] NOT NULL DEFAULT '{}',
  jurisdictions text[] NOT NULL DEFAULT '{}',
  ingestion_method text NOT NULL,
  license_type text NOT NULL CHECK (license_type IN ('A', 'B', 'C', 'D', 'E')),
  commercial_use_allowed boolean NOT NULL DEFAULT false,
  attribution_required boolean NOT NULL DEFAULT true,
  crawl_allowed boolean NOT NULL DEFAULT false,
  refresh_frequency text NOT NULL,
  authority_score double precision NOT NULL DEFAULT 0.8
    CHECK (authority_score >= 0 AND authority_score <= 1),
  quality_score double precision NOT NULL DEFAULT 0.8
    CHECK (quality_score >= 0 AND quality_score <= 1),
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'paused', 'retired')),
  namespace text NOT NULL DEFAULT 'platform_shared'
    CHECK (namespace = 'platform_shared'),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  last_refreshed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT knowledge_sources_type_d_live_only CHECK (
    license_type <> 'D'
    OR (ingestion_method = 'live_only' AND crawl_allowed = false)
  )
);

CREATE TABLE IF NOT EXISTS public.knowledge_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id uuid NOT NULL REFERENCES public.knowledge_sources(id) ON DELETE CASCADE,
  external_id text NOT NULL,
  title text NOT NULL,
  published_at timestamptz,
  effective_at timestamptz,
  superseded_at timestamptz,
  checksum text,
  version_label text,
  citation text,
  jurisdiction text,
  topics text[] NOT NULL DEFAULT '{}',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_source
  ON public.knowledge_documents (source_id);

CREATE TABLE IF NOT EXISTS public.knowledge_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES public.knowledge_documents(id) ON DELETE CASCADE,
  source_id uuid NOT NULL REFERENCES public.knowledge_sources(id) ON DELETE CASCADE,
  chunk_index int NOT NULL,
  content text NOT NULL,
  embedding vector(1536),
  model_version text,
  entities text[] NOT NULL DEFAULT '{}',
  topics text[] NOT NULL DEFAULT '{}',
  jurisdiction text,
  authority_score double precision NOT NULL DEFAULT 0.8
    CHECK (authority_score >= 0 AND authority_score <= 1),
  freshness_score double precision NOT NULL DEFAULT 0.8
    CHECK (freshness_score >= 0 AND freshness_score <= 1),
  citation text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_source
  ON public.knowledge_chunks (source_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document
  ON public.knowledge_chunks (document_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_jurisdiction
  ON public.knowledge_chunks (jurisdiction);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding_hnsw
  ON public.knowledge_chunks
  USING hnsw (embedding vector_cosine_ops)
  WHERE embedding IS NOT NULL;

-- Full-text for hybrid / BM25-style ranking
ALTER TABLE public.knowledge_chunks
  ADD COLUMN IF NOT EXISTS content_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED;

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_fts
  ON public.knowledge_chunks USING gin (content_tsv);

-- RLS: shared packs are readable by authenticated users; never written via JWT role.
-- Customer private RAG remains on rag_* with org_id isolation — no FK/join between them.
ALTER TABLE public.knowledge_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_chunks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS knowledge_sources_authenticated_read ON public.knowledge_sources;
CREATE POLICY knowledge_sources_authenticated_read
  ON public.knowledge_sources FOR SELECT TO authenticated
  USING (namespace = 'platform_shared' AND status = 'active');

DROP POLICY IF EXISTS knowledge_documents_authenticated_read ON public.knowledge_documents;
CREATE POLICY knowledge_documents_authenticated_read
  ON public.knowledge_documents FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.knowledge_sources s
      WHERE s.id = knowledge_documents.source_id
        AND s.namespace = 'platform_shared'
        AND s.status = 'active'
    )
  );

DROP POLICY IF EXISTS knowledge_chunks_authenticated_read ON public.knowledge_chunks;
CREATE POLICY knowledge_chunks_authenticated_read
  ON public.knowledge_chunks FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.knowledge_sources s
      WHERE s.id = knowledge_chunks.source_id
        AND s.namespace = 'platform_shared'
        AND s.status = 'active'
    )
  );

-- No INSERT/UPDATE/DELETE policies for authenticated → writes denied under RLS.
-- Ingest uses service role (bypasses RLS). Customer private content stays on rag_* only.

COMMENT ON TABLE public.knowledge_sources IS
  'Platform-shared knowledge fabric sources. Structurally separate from org-scoped rag_sources.';
COMMENT ON TABLE public.knowledge_chunks IS
  'Platform-shared chunks + 1536-d OpenAI embeddings. Never store customer-private content here.';
-- Vector match helper for knowledge fabric (platform shared only)
CREATE OR REPLACE FUNCTION public.match_knowledge_chunks(
  query_embedding vector(1536),
  match_count int DEFAULT 12,
  source_ids uuid[] DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  content text,
  citation text,
  jurisdiction text,
  authority_score double precision,
  freshness_score double precision,
  topics text[],
  source_id uuid,
  document_id uuid,
  metadata jsonb,
  similarity double precision
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    c.id,
    c.content,
    c.citation,
    c.jurisdiction,
    c.authority_score,
    c.freshness_score,
    c.topics,
    c.source_id,
    c.document_id,
    c.metadata,
    (1 - (c.embedding <=> query_embedding))::double precision AS similarity
  FROM public.knowledge_chunks c
  JOIN public.knowledge_sources s ON s.id = c.source_id
  WHERE s.namespace = 'platform_shared'
    AND s.status = 'active'
    AND c.embedding IS NOT NULL
    AND (source_ids IS NULL OR c.source_id = ANY (source_ids))
  ORDER BY c.embedding <=> query_embedding
  LIMIT greatest(match_count, 1);
$$;

-- Phase 7: Multi-environment isolation (per org)

CREATE TABLE public.environments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  config_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_environments_org_name ON public.environments(org_id, name);

ALTER TABLE public.environments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "environments_org"
  ON public.environments FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

-- Default environment for existing orgs
INSERT INTO public.environments (org_id, name)
SELECT id, 'default' FROM public.organizations
ON CONFLICT DO NOTHING;

ALTER TABLE public.workflow_runs
  ADD COLUMN IF NOT EXISTS environment text NOT NULL DEFAULT 'default';

ALTER TABLE public.connectors
  ADD COLUMN IF NOT EXISTS environment text NOT NULL DEFAULT 'default';

ALTER TABLE public.rag_sources
  ADD COLUMN IF NOT EXISTS environment text NOT NULL DEFAULT 'default';

ALTER TABLE public.rag_documents
  ADD COLUMN IF NOT EXISTS environment text NOT NULL DEFAULT 'default';

ALTER TABLE public.rag_chunks
  ADD COLUMN IF NOT EXISTS environment text NOT NULL DEFAULT 'default';

ALTER TABLE public.rag_embeddings
  ADD COLUMN IF NOT EXISTS environment text NOT NULL DEFAULT 'default';

ALTER TABLE public.rag_ingest_jobs
  ADD COLUMN IF NOT EXISTS environment text NOT NULL DEFAULT 'default';

ALTER TABLE public.rag_retrieval_logs
  ADD COLUMN IF NOT EXISTS environment text NOT NULL DEFAULT 'default';

CREATE INDEX IF NOT EXISTS idx_workflow_runs_org_env_created
  ON public.workflow_runs(org_id, environment, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_connectors_org_env
  ON public.connectors(org_id, environment);

CREATE INDEX IF NOT EXISTS idx_rag_sources_org_env
  ON public.rag_sources(org_id, environment);

CREATE INDEX IF NOT EXISTS idx_rag_documents_org_env
  ON public.rag_documents(org_id, environment);

CREATE INDEX IF NOT EXISTS idx_rag_ingest_jobs_org_env_created
  ON public.rag_ingest_jobs(org_id, environment, created_at DESC);

-- Update rag_search to filter by environment
CREATE OR REPLACE FUNCTION public.rag_search(
  p_org_id uuid,
  p_query_embedding text,
  p_top_k int,
  p_source_id uuid DEFAULT NULL,
  p_document_id uuid DEFAULT NULL,
  p_environment text DEFAULT 'default'
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
  ORDER BY e.embedding <=> (p_query_embedding::vector(1536))
  LIMIT p_top_k;
$$;

-- Update ingest job claim function to return environment
CREATE OR REPLACE FUNCTION public.claim_rag_ingest_job()
RETURNS TABLE (
  id uuid,
  org_id uuid,
  source_id uuid,
  external_id text,
  created_by uuid,
  environment text,
  request_payload jsonb
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_job_id uuid;
BEGIN
  SELECT j.id
    INTO v_job_id
  FROM public.rag_ingest_jobs j
  WHERE j.status = 'queued'
  ORDER BY j.created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED;

  IF v_job_id IS NULL THEN
    RETURN;
  END IF;

  RETURN QUERY
  UPDATE public.rag_ingest_jobs
     SET status = 'running',
         started_at = now(),
         updated_at = now()
   WHERE id = v_job_id
  RETURNING id, org_id, source_id, external_id, created_by, environment, request_payload;
END;
$$;

-- DC-00: Optional ingestion job tracking for controlled ingestion
-- Authority: docs/phase-3/DC-00_IMPLEMENTATION.md

CREATE TABLE public.rag_ingest_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  source_id uuid NOT NULL REFERENCES public.rag_sources(id) ON DELETE CASCADE,
  document_id uuid REFERENCES public.rag_documents(id) ON DELETE SET NULL,
  external_id text,
  status text NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
  chunk_count int NOT NULL DEFAULT 0,
  model text,
  dimension int,
  error_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  completed_at timestamptz,
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL
);

CREATE INDEX idx_rag_ingest_jobs_org_created ON public.rag_ingest_jobs(org_id, created_at DESC);
CREATE INDEX idx_rag_ingest_jobs_source_created ON public.rag_ingest_jobs(source_id, created_at DESC);

ALTER TABLE public.rag_ingest_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "rag_ingest_jobs_org"
  ON public.rag_ingest_jobs FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

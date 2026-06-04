-- STA-45: Knowledge sync scheduler jobs (Notion / future CRM→RAG sources)

CREATE TABLE IF NOT EXISTS public.knowledge_sync_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  connector_id uuid NOT NULL REFERENCES public.connectors(id) ON DELETE CASCADE,
  source_type text NOT NULL,
  environment text NOT NULL DEFAULT 'production',
  status text NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'running', 'completed', 'failed', 'skipped')),
  trigger_type text NOT NULL DEFAULT 'schedule'
    CHECK (trigger_type IN ('schedule', 'manual', 'webhook')),
  scheduled_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  completed_at timestamptz,
  pages_synced int NOT NULL DEFAULT 0,
  ingest_jobs_queued int NOT NULL DEFAULT 0,
  chunks_added int NOT NULL DEFAULT 0,
  error_message text,
  result jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_sync_jobs_org_created
  ON public.knowledge_sync_jobs(org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_knowledge_sync_jobs_connector_created
  ON public.knowledge_sync_jobs(connector_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_knowledge_sync_jobs_status_scheduled
  ON public.knowledge_sync_jobs(status, scheduled_at);

ALTER TABLE public.knowledge_sync_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "knowledge_sync_jobs_org"
  ON public.knowledge_sync_jobs FOR ALL
  USING (
    org_id IN (
      SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.knowledge_sync_jobs IS
  'Unified knowledge-source sync runs (Notion→RAG, future HubSpot/Zendesk).';

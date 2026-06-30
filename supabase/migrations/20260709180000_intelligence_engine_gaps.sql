-- Gravitre Intelligence Engine gap closure: org engine settings, pipeline latency, feedback corrections

CREATE TABLE IF NOT EXISTS public.org_intelligence_engine_settings (
  org_id uuid PRIMARY KEY REFERENCES public.organizations(id) ON DELETE CASCADE,
  validation_enabled boolean NOT NULL DEFAULT true,
  reranking_enabled boolean NOT NULL DEFAULT true,
  confidence_threshold double precision NOT NULL DEFAULT 0.4
    CHECK (confidence_threshold >= 0 AND confidence_threshold <= 1),
  max_chunks integer NOT NULL DEFAULT 8 CHECK (max_chunks >= 1 AND max_chunks <= 50),
  connector_timeout_seconds integer NOT NULL DEFAULT 30
    CHECK (connector_timeout_seconds >= 5 AND connector_timeout_seconds <= 300),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.org_intelligence_engine_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_intelligence_engine_settings_org ON public.org_intelligence_engine_settings;
CREATE POLICY org_intelligence_engine_settings_org
  ON public.org_intelligence_engine_settings FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

CREATE TABLE IF NOT EXISTS public.ai_pipeline_latency (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  message_id uuid,
  stage_name text NOT NULL,
  duration_ms integer NOT NULL CHECK (duration_ms >= 0),
  cache_hit boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_pipeline_latency_org_created
  ON public.ai_pipeline_latency (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_pipeline_latency_message
  ON public.ai_pipeline_latency (message_id)
  WHERE message_id IS NOT NULL;

ALTER TABLE public.ai_pipeline_latency ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_pipeline_latency_org ON public.ai_pipeline_latency;
CREATE POLICY ai_pipeline_latency_org
  ON public.ai_pipeline_latency FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

ALTER TABLE public.message_feedback
  ADD COLUMN IF NOT EXISTS corrected_answer text;

COMMENT ON TABLE public.org_intelligence_engine_settings IS
  'Per-org Gravitre Intelligence Engine tuning (validation, rerank, confidence, retrieval limits).';

COMMENT ON TABLE public.ai_pipeline_latency IS
  'Per-stage pipeline latency for intelligence runs (retrieval, rerank, generation, validation).';

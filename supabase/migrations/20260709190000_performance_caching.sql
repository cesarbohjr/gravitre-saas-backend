-- Performance tier caching + dashboard extensions

ALTER TABLE public.org_intelligence_engine_settings
  ADD COLUMN IF NOT EXISTS performance_mode text NOT NULL DEFAULT 'balanced'
    CHECK (performance_mode IN ('speed_priority', 'balanced', 'accuracy_priority'));

ALTER TABLE public.ai_pipeline_latency
  ADD COLUMN IF NOT EXISTS tier text,
  ADD COLUMN IF NOT EXISTS model_used text,
  ADD COLUMN IF NOT EXISTS estimated_cost_usd numeric(10, 6);

CREATE INDEX IF NOT EXISTS idx_ai_pipeline_latency_org_stage
  ON public.ai_pipeline_latency (org_id, stage_name, created_at DESC);

COMMENT ON COLUMN public.org_intelligence_engine_settings.performance_mode IS
  'Org latency-vs-accuracy preference: speed_priority | balanced | accuracy_priority';

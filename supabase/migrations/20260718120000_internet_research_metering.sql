-- Internet research: Research Lookup metering + platform grounding volume monitor

ALTER TABLE public.usage_records
  DROP CONSTRAINT IF EXISTS usage_records_metric_type_check;

ALTER TABLE public.usage_records
  ADD CONSTRAINT usage_records_metric_type_check
  CHECK (metric_type IN ('workflow_runs', 'ai_tokens', 'outputs', 'api_calls', 'research_lookups'));

ALTER TABLE public.usage_records
  ADD COLUMN IF NOT EXISTS metadata jsonb;

ALTER TABLE public.usage_records
  ADD COLUMN IF NOT EXISTS idempotency_key text;

CREATE UNIQUE INDEX IF NOT EXISTS idx_usage_records_org_idempotency
  ON public.usage_records (org_id, idempotency_key)
  WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.platform_grounding_daily (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usage_date date NOT NULL UNIQUE,
  grounding_count integer NOT NULL DEFAULT 0 CHECK (grounding_count >= 0),
  alert_sent_at timestamptz,
  last_alert_severity text,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_platform_grounding_daily_date
  ON public.platform_grounding_daily (usage_date DESC);

CREATE TABLE IF NOT EXISTS public.org_research_lookup_daily (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  usage_date date NOT NULL,
  lookup_count integer NOT NULL DEFAULT 0 CHECK (lookup_count >= 0),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, usage_date)
);

CREATE INDEX IF NOT EXISTS idx_org_research_lookup_daily_org_date
  ON public.org_research_lookup_daily (org_id, usage_date DESC);

ALTER TABLE public.platform_grounding_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.org_research_lookup_daily ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "platform_grounding_daily_service" ON public.platform_grounding_daily;
CREATE POLICY "platform_grounding_daily_service"
  ON public.platform_grounding_daily FOR ALL
  USING (true)
  WITH CHECK (true);

DROP POLICY IF EXISTS "org_research_lookup_daily_org_scope" ON public.org_research_lookup_daily;
CREATE POLICY "org_research_lookup_daily_org_scope"
  ON public.org_research_lookup_daily FOR ALL
  USING (org_id = (current_setting('request.jwt.claims', true)::json->>'org_id')::uuid)
  WITH CHECK (org_id = (current_setting('request.jwt.claims', true)::json->>'org_id')::uuid);

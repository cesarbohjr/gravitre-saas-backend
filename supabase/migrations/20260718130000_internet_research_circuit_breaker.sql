-- Per-org hourly grounding circuit breaker (hard limit; independent of 75% platform alert)

CREATE TABLE IF NOT EXISTS public.org_grounding_hourly (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  hour_bucket timestamptz NOT NULL,
  grounding_count integer NOT NULL DEFAULT 0 CHECK (grounding_count >= 0),
  circuit_opened_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, hour_bucket)
);

CREATE INDEX IF NOT EXISTS idx_org_grounding_hourly_org_bucket
  ON public.org_grounding_hourly (org_id, hour_bucket DESC);

ALTER TABLE public.org_grounding_hourly ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "org_grounding_hourly_org_scope" ON public.org_grounding_hourly;
CREATE POLICY "org_grounding_hourly_org_scope"
  ON public.org_grounding_hourly FOR ALL
  USING (org_id = (current_setting('request.jwt.claims', true)::json->>'org_id')::uuid)
  WITH CHECK (org_id = (current_setting('request.jwt.claims', true)::json->>'org_id')::uuid);

-- Research Lookups: single source of truth on billing_plans (allotments + overage rate)
-- Aligns with output/meson keys in overage_rates and outputs_per_month in features.

UPDATE public.billing_plans
SET
  features = features || '{"research_lookups_per_month": 10}'::jsonb,
  overage_rates = overage_rates || '{"research_lookup": 0.35}'::jsonb
WHERE code = 'node';

UPDATE public.billing_plans
SET
  features = features || '{"research_lookups_per_month": 60}'::jsonb,
  overage_rates = overage_rates || '{"research_lookup": 0.35}'::jsonb
WHERE code = 'control';

UPDATE public.billing_plans
SET
  features = features || '{"research_lookups_per_month": 200}'::jsonb,
  overage_rates = overage_rates || '{"research_lookup": 0.35}'::jsonb
WHERE code = 'command';

UPDATE public.billing_plans
SET
  features = features || '{"research_lookups_per_month": 200}'::jsonb,
  overage_rates = COALESCE(overage_rates, '{}'::jsonb) || '{"research_lookup": 0.35}'::jsonb
WHERE code = 'enterprise';

-- Stripe reporting marker for research_lookups usage_records rows
ALTER TABLE public.usage_records
  ADD COLUMN IF NOT EXISTS stripe_reported_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_usage_records_research_stripe_pending
  ON public.usage_records (org_id, recorded_at DESC)
  WHERE metric_type = 'research_lookups' AND stripe_reported_at IS NULL;

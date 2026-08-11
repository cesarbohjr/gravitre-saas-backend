-- Restore Research Lookups allotments/overage wiped by
-- 20260729120000_seed_all_billing_plans.sql (ON CONFLICT replaced features/
-- overage_rates wholesale without research keys). Voice keys survived because
-- 20260808120000 merged them after that overwrite.
--
-- Idempotent jsonb merge — same shape as 20260719120000.

UPDATE public.billing_plans
SET
  features = COALESCE(features, '{}'::jsonb) || '{"research_lookups_per_month": 10}'::jsonb,
  overage_rates = COALESCE(overage_rates, '{}'::jsonb) || '{"research_lookup": 0.35}'::jsonb
WHERE lower(code) IN ('node', 'starter', 'free');

UPDATE public.billing_plans
SET
  features = COALESCE(features, '{}'::jsonb) || '{"research_lookups_per_month": 60}'::jsonb,
  overage_rates = COALESCE(overage_rates, '{}'::jsonb) || '{"research_lookup": 0.35}'::jsonb
WHERE lower(code) IN ('control', 'growth');

UPDATE public.billing_plans
SET
  features = COALESCE(features, '{}'::jsonb) || '{"research_lookups_per_month": 200}'::jsonb,
  overage_rates = COALESCE(overage_rates, '{}'::jsonb) || '{"research_lookup": 0.35}'::jsonb
WHERE lower(code) IN ('command', 'scale', 'enterprise');

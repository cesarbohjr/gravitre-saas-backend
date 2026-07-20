-- Post-migration verification for 20260719120000_billing_plans_research_lookups.sql
SELECT
  code,
  features -> 'research_lookups_per_month' AS research_lookups_per_month,
  overage_rates -> 'research_lookup' AS research_lookup_overage_usd
FROM public.billing_plans
WHERE code IN ('node', 'control', 'command', 'enterprise')
ORDER BY code;

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'usage_records'
  AND column_name = 'stripe_reported_at';

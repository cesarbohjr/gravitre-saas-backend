-- Seed the full set of billing plans into production.
--
-- Root cause this fixes: the auth/onboarding bootstrap migration
-- (20260529120000) seeds ONLY the 'node' plan into public.billing_plans.
-- The 'control', 'command', and 'enterprise' plans live exclusively in
-- supabase/seed.sql, which only runs on a local `supabase db reset` and is
-- NEVER applied to hosted environments. Because public.org_billing.plan_code
-- is a FOREIGN KEY to public.billing_plans(code), any checkout/subscribe for
-- 'control' or 'command' on a brand-new org (one with no org_billing row yet)
-- fails when _create_stripe_customer upserts org_billing with the missing
-- plan_code, raising a foreign-key violation that surfaces as a generic
-- INTERNAL_ERROR 500 and a dead upgrade button.
--
-- This migration is idempotent (ON CONFLICT ... DO UPDATE) and keeps the plan
-- catalog in sync with supabase/seed.sql on every deploy.

INSERT INTO public.billing_plans (
  code,
  name,
  price_usd,
  agents_limit,
  workflows_limit,
  environments_limit,
  ai_credits_included,
  workflow_runs_included,
  features,
  overage_rates
) VALUES
  (
    'node',
    'Node',
    49,
    1,
    10,
    1,
    1000,
    500,
    '{"outputs_per_month": 10, "core_users": 1, "lite_users": 2, "meson": false, "email_delivery": true, "basic_campaigns": true, "integrations": 3, "support": "community", "research_lookups_per_month": 10, "voice_minutes_per_month": 60}'::jsonb,
    '{"output": 2.50, "meson": null, "research_lookup": 0.35, "voice_minute": 0.12}'::jsonb
  ),
  (
    'control',
    'Control',
    129,
    3,
    40,
    2,
    5000,
    2500,
    '{"outputs_per_month": 40, "core_users": 2, "lite_users": 5, "meson": 10, "crm_integration": true, "outlook_integration": true, "multi_step_execution": true, "full_campaigns": true, "slack_delivery": true, "support": "priority", "research_lookups_per_month": 60, "voice_minutes_per_month": 300}'::jsonb,
    '{"output": 2.00, "meson": 3.00, "research_lookup": 0.35, "voice_minute": 0.12}'::jsonb
  ),
  (
    'command',
    'Command',
    299,
    8,
    120,
    5,
    15000,
    10000,
    '{"outputs_per_month": 120, "core_users": 5, "lite_users": -1, "meson": 40, "approvals": true, "advanced_integrations": true, "team_workspace": true, "cross_department_agents": true, "custom_agent_training": true, "support": "dedicated", "research_lookups_per_month": 200, "voice_minutes_per_month": 1200}'::jsonb,
    '{"output": 1.50, "meson": 2.00, "research_lookup": 0.35, "voice_minute": 0.12}'::jsonb
  ),
  (
    'enterprise',
    'Enterprise',
    NULL,
    NULL,
    NULL,
    NULL,
    0,
    0,
    '{"outputs_per_month": -1, "core_users": -1, "lite_users": -1, "meson": -1, "custom": true, "sla": true, "dedicated_support": true, "sso": true, "audit_logs": true, "research_lookups_per_month": 200, "voice_minutes_per_month": 1200}'::jsonb,
    '{"research_lookup": 0.35, "voice_minute": 0.12}'::jsonb
  )
ON CONFLICT (code) DO UPDATE SET
  name = EXCLUDED.name,
  price_usd = EXCLUDED.price_usd,
  agents_limit = EXCLUDED.agents_limit,
  workflows_limit = EXCLUDED.workflows_limit,
  environments_limit = EXCLUDED.environments_limit,
  ai_credits_included = EXCLUDED.ai_credits_included,
  workflow_runs_included = EXCLUDED.workflow_runs_included,
  -- Merge (do not replace) so additive entitlement keys cannot be wiped again.
  features = COALESCE(public.billing_plans.features, '{}'::jsonb) || EXCLUDED.features,
  overage_rates = COALESCE(public.billing_plans.overage_rates, '{}'::jsonb) || EXCLUDED.overage_rates;

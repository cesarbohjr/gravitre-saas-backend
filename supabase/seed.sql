-- Optional dev seed data
-- Billing plans (MVP)
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
    'starter',
    'Starter',
    79,
    3,
    10,
    1,
    2000,
    1000,
    '{"approvals": false, "audit_logs": false, "versioning": false, "advanced_connectors": false}'::jsonb,
    '{"ai_credit": 0.02, "workflow_runs_per_1000": 10}'::jsonb
  ),
  (
    'growth',
    'Growth',
    299,
    15,
    50,
    2,
    15000,
    10000,
    '{"approvals": true, "audit_logs": "basic", "versioning": true, "advanced_connectors": false}'::jsonb,
    '{"ai_credit": 0.015, "workflow_runs_per_1000": 8}'::jsonb
  ),
  (
    'scale',
    'Scale',
    999,
    50,
    NULL,
    5,
    75000,
    50000,
    '{"approvals": "advanced", "audit_logs": "full", "versioning": "full", "advanced_connectors": true, "rbac": true}'::jsonb,
    '{"ai_credit": 0.012, "workflow_runs_per_1000": 5}'::jsonb
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
    '{"approvals": "custom", "audit_logs": "custom", "versioning": "custom", "advanced_connectors": true, "rbac": true}'::jsonb,
    '{}'::jsonb
  )
ON CONFLICT (code) DO UPDATE SET
  name = EXCLUDED.name,
  price_usd = EXCLUDED.price_usd,
  agents_limit = EXCLUDED.agents_limit,
  workflows_limit = EXCLUDED.workflows_limit,
  environments_limit = EXCLUDED.environments_limit,
  ai_credits_included = EXCLUDED.ai_credits_included,
  workflow_runs_included = EXCLUDED.workflow_runs_included,
  features = EXCLUDED.features,
  overage_rates = EXCLUDED.overage_rates;

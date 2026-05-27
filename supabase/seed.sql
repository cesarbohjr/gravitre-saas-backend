-- Optional dev seed data
-- Billing plans (aligned with pricing page: Node, Control, Command)
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
    '{"outputs_per_month": 10, "core_users": 1, "lite_users": 2, "meson": false, "email_delivery": true, "basic_campaigns": true, "integrations": 3, "support": "community"}'::jsonb,
    '{"output": 2.50, "meson": null}'::jsonb
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
    '{"outputs_per_month": 40, "core_users": 2, "lite_users": 5, "meson": 10, "crm_integration": true, "outlook_integration": true, "multi_step_execution": true, "full_campaigns": true, "slack_delivery": true, "support": "priority"}'::jsonb,
    '{"output": 2.00, "meson": 3.00}'::jsonb
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
    '{"outputs_per_month": 120, "core_users": 5, "lite_users": -1, "meson": 40, "approvals": true, "advanced_integrations": true, "team_workspace": true, "cross_department_agents": true, "custom_agent_training": true, "support": "dedicated"}'::jsonb,
    '{"output": 1.50, "meson": 2.00}'::jsonb
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
    '{"outputs_per_month": -1, "core_users": -1, "lite_users": -1, "meson": -1, "custom": true, "sla": true, "dedicated_support": true, "sso": true, "audit_logs": true}'::jsonb,
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

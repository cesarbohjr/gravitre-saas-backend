-- Ensure billing_plans feature flags include advanced_connectors for paid tiers.

UPDATE public.billing_plans
SET features = features || '{"advanced_connectors": true}'::jsonb
WHERE code IN ('node', 'starter', 'control', 'growth', 'command', 'scale', 'enterprise');

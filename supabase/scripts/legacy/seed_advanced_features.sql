-- ============================================================
-- Gravitre Advanced Features Seed (Idempotent)
-- ============================================================
-- Seeds advanced feature tables for v0 backend/API integration.
-- Uses fixed UUIDs and ON CONFLICT DO NOTHING.

WITH demo_org AS (
  SELECT id
  FROM public.organizations
  WHERE id = '00000000-0000-0000-0000-000000000001'
)
INSERT INTO public.goals (
  id,
  org_id,
  objective,
  category,
  priority,
  frequency,
  department,
  success_metrics,
  connected_systems,
  status,
  created_at,
  updated_at
)
SELECT
  'aaaaaaa1-1111-4111-8111-111111111111',
  demo_org.id,
  'Reduce approval bottlenecks in high-priority workflows',
  'operations',
  'high',
  'weekly',
  'operations',
  '{"targetApprovalMinutes":45,"baselineApprovalMinutes":93,"owner":"Nexus"}'::jsonb,
  ARRAY['slack','postgres'],
  'active',
  now() - interval '6 days',
  now()
FROM demo_org
ON CONFLICT (id) DO NOTHING;

WITH demo_org AS (
  SELECT id
  FROM public.organizations
  WHERE id = '00000000-0000-0000-0000-000000000001'
)
INSERT INTO public.goals (
  id,
  org_id,
  objective,
  category,
  priority,
  frequency,
  department,
  success_metrics,
  connected_systems,
  status,
  created_at,
  updated_at
)
SELECT
  'aaaaaaa2-2222-4222-8222-222222222222',
  demo_org.id,
  'Improve connector reliability above 99% success rate',
  'reliability',
  'high',
  'daily',
  'platform',
  '{"targetSuccessRate":99,"baselineSuccessRate":94.7}'::jsonb,
  ARRAY['salesforce','hubspot','slack'],
  'active',
  now() - interval '4 days',
  now()
FROM demo_org
ON CONFLICT (id) DO NOTHING;

WITH demo_org AS (
  SELECT id
  FROM public.organizations
  WHERE id = '00000000-0000-0000-0000-000000000001'
)
INSERT INTO public.goal_plans (
  id,
  org_id,
  goal_id,
  proposed_steps,
  required_connectors,
  required_agents,
  approval_gates,
  estimated_impact,
  created_at,
  updated_at
)
SELECT
  'bbbbbbb1-1111-4111-8111-111111111111',
  demo_org.id,
  'aaaaaaa1-1111-4111-8111-111111111111',
  '[{"id":"step-1","title":"Map approval paths"},{"id":"step-2","title":"Enable auto-routing"},{"id":"step-3","title":"Measure SLA improvements"}]'::jsonb,
  ARRAY['slack','postgres'],
  ARRAY[]::uuid[],
  '[{"phase":"prelaunch","approverRole":"owner"},{"phase":"rollout","approverRole":"operator"}]'::jsonb,
  '{"confidence":0.74,"expectedLift":"18% faster approvals"}'::jsonb,
  now() - interval '3 days',
  now()
FROM demo_org
WHERE EXISTS (
  SELECT 1 FROM public.goals WHERE id = 'aaaaaaa1-1111-4111-8111-111111111111'
)
ON CONFLICT (id) DO NOTHING;

WITH demo_org AS (
  SELECT id
  FROM public.organizations
  WHERE id = '00000000-0000-0000-0000-000000000001'
),
first_run AS (
  SELECT id
  FROM public.runs
  WHERE org_id = '00000000-0000-0000-0000-000000000001'
  ORDER BY created_at DESC
  LIMIT 1
)
INSERT INTO public.council_sessions (
  id,
  org_id,
  workflow_run_id,
  objective,
  participating_agents,
  debate_mode,
  status,
  final_decision,
  dissenting_opinions,
  created_at,
  updated_at
)
SELECT
  'ccccccc1-1111-4111-8111-111111111111',
  demo_org.id,
  (SELECT id FROM first_run),
  'Choose safest optimization rollout plan for sync workflow',
  '[{"id":"agent-atlas","name":"Atlas"},{"id":"agent-nexus","name":"Nexus"},{"id":"agent-sentinel","name":"Sentinel"}]'::jsonb,
  'consensus',
  'resolved',
  '{"recommendation":"Phased rollout with monitoring gates","confidence":0.81,"method":"consensus"}'::jsonb,
  '[{"agent":"Sentinel","reason":"Requested additional validation period"}]'::jsonb,
  now() - interval '2 days',
  now()
FROM demo_org
ON CONFLICT (id) DO NOTHING;

WITH demo_org AS (
  SELECT id
  FROM public.organizations
  WHERE id = '00000000-0000-0000-0000-000000000001'
)
INSERT INTO public.council_contributions (
  id,
  org_id,
  session_id,
  agent_id,
  position,
  confidence,
  reasoning,
  evidence_used,
  created_at
)
SELECT
  'ddddddd1-1111-4111-8111-111111111111',
  demo_org.id,
  'ccccccc1-1111-4111-8111-111111111111',
  NULL,
  'Proceed with phased rollout in staging first',
  0.84,
  'Current error trend is low and recovery playbooks are in place.',
  '["health-score-trend","approval-latency"]'::jsonb,
  now() - interval '2 days'
FROM demo_org
WHERE EXISTS (
  SELECT 1 FROM public.council_sessions WHERE id = 'ccccccc1-1111-4111-8111-111111111111'
)
ON CONFLICT (id) DO NOTHING;

WITH demo_org AS (
  SELECT id
  FROM public.organizations
  WHERE id = '00000000-0000-0000-0000-000000000001'
)
INSERT INTO public.council_contributions (
  id,
  org_id,
  session_id,
  agent_id,
  position,
  confidence,
  reasoning,
  evidence_used,
  created_at
)
SELECT
  'ddddddd2-2222-4222-8222-222222222222',
  demo_org.id,
  'ccccccc1-1111-4111-8111-111111111111',
  NULL,
  'Require additional validation and one-week guardrail period',
  0.67,
  'Recent connector failures suggest extra caution before full rollout.',
  '["connector-error-log","incident-summary"]'::jsonb,
  now() - interval '2 days'
FROM demo_org
WHERE EXISTS (
  SELECT 1 FROM public.council_sessions WHERE id = 'ccccccc1-1111-4111-8111-111111111111'
)
ON CONFLICT (id) DO NOTHING;

WITH demo_org AS (
  SELECT id
  FROM public.organizations
  WHERE id = '00000000-0000-0000-0000-000000000001'
),
workflow_ref AS (
  SELECT id
  FROM public.workflows
  WHERE org_id = '00000000-0000-0000-0000-000000000001'
  ORDER BY created_at DESC
  LIMIT 1
)
INSERT INTO public.workflow_health_snapshots (
  id,
  org_id,
  workflow_id,
  score,
  dimensions,
  recorded_at
)
SELECT
  'eeeeeee1-1111-4111-8111-111111111111',
  demo_org.id,
  (SELECT id FROM workflow_ref),
  78,
  '{"reliability":82,"speed":74,"costEfficiency":71,"overrideRate":29,"goalCompletion":76,"decisionAccuracy":80}'::jsonb,
  now() - interval '6 days'
FROM demo_org
ON CONFLICT (id) DO NOTHING;

WITH demo_org AS (
  SELECT id
  FROM public.organizations
  WHERE id = '00000000-0000-0000-0000-000000000001'
),
workflow_ref AS (
  SELECT id
  FROM public.workflows
  WHERE org_id = '00000000-0000-0000-0000-000000000001'
  ORDER BY created_at DESC
  LIMIT 1
)
INSERT INTO public.workflow_health_snapshots (
  id,
  org_id,
  workflow_id,
  score,
  dimensions,
  recorded_at
)
SELECT
  'eeeeeee2-2222-4222-8222-222222222222',
  demo_org.id,
  (SELECT id FROM workflow_ref),
  84,
  '{"reliability":88,"speed":79,"costEfficiency":75,"overrideRate":21,"goalCompletion":83,"decisionAccuracy":86}'::jsonb,
  now() - interval '1 day'
FROM demo_org
ON CONFLICT (id) DO NOTHING;

WITH demo_org AS (
  SELECT id
  FROM public.organizations
  WHERE id = '00000000-0000-0000-0000-000000000001'
),
workflow_ref AS (
  SELECT id
  FROM public.workflows
  WHERE org_id = '00000000-0000-0000-0000-000000000001'
  ORDER BY created_at DESC
  LIMIT 1
)
INSERT INTO public.optimization_recommendations (
  id,
  org_id,
  workflow_id,
  issue,
  evidence,
  suggested_change,
  estimated_impact,
  confidence,
  risk_level,
  status,
  affected_nodes,
  created_at,
  updated_at
)
SELECT
  'fffffff1-1111-4111-8111-111111111111',
  demo_org.id,
  (SELECT id FROM workflow_ref),
  'Approval queue latency spikes during peak hours',
  'Median queue wait exceeds 70 minutes between 13:00-16:00 UTC.',
  '{"change":"enable-priority-routing","config":{"window":"peak-hours"}}'::jsonb,
  '{"approvalMinutesReduction":"20-30%","throughputIncrease":"12%"}'::jsonb,
  0.79,
  'medium',
  'open',
  ARRAY['approval-gate','router-node'],
  now() - interval '20 hours',
  now()
FROM demo_org
ON CONFLICT (id) DO NOTHING;

WITH demo_org AS (
  SELECT id
  FROM public.organizations
  WHERE id = '00000000-0000-0000-0000-000000000001'
),
workflow_ref AS (
  SELECT id
  FROM public.workflows
  WHERE org_id = '00000000-0000-0000-0000-000000000001'
  ORDER BY created_at DESC
  LIMIT 1
)
INSERT INTO public.workflow_ab_tests (
  id,
  org_id,
  workflow_id,
  version_a,
  version_b,
  traffic_split,
  metrics,
  status,
  created_at,
  updated_at
)
SELECT
  '99999991-1111-4111-8111-111111111111',
  demo_org.id,
  (SELECT id FROM workflow_ref),
  3,
  4,
  '{"a":50,"b":50}'::jsonb,
  '{"primary":"completion_rate","secondary":["latency","override_rate"]}'::jsonb,
  'draft',
  now() - interval '8 hours',
  now()
FROM demo_org
ON CONFLICT (id) DO NOTHING;

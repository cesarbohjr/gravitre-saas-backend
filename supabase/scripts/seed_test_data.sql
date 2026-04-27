-- ============================================================
-- Gravitre Contract Seed Data (Idempotent)
-- ============================================================
-- Non-destructive seed for frontend contract tables.
-- Uses fixed UUIDs and ON CONFLICT DO NOTHING for idempotency.

-- 1) organizations (expected total: 1)
INSERT INTO public.organizations (
  id,
  name,
  slug,
  settings,
  status,
  created_at,
  updated_at
)
VALUES (
  '11111111-1111-4111-8111-111111111111',
  'Gravitre Labs',
  'gravitre-labs',
  '{"theme":"dark","timezone":"UTC","locale":"en-US"}'::jsonb,
  'active',
  now() - interval '7 days',
  now()
)
ON CONFLICT (id) DO NOTHING;

-- 2) users (expected total: 1)
INSERT INTO public.users (
  id,
  org_id,
  auth_user_id,
  email,
  full_name,
  role,
  status,
  created_at,
  updated_at
)
VALUES (
  '22222222-2222-4222-8222-222222222222',
  '11111111-1111-4111-8111-111111111111',
  NULL,
  'operator@gravitre.ai',
  'Gravitre Operator',
  'owner',
  'active',
  now() - interval '7 days',
  now()
)
ON CONFLICT (id) DO NOTHING;

-- 3) agents (expected total: 4)
INSERT INTO public.agents (
  id,
  org_id,
  name,
  purpose,
  role,
  model,
  capabilities,
  systems,
  guardrails,
  config,
  status,
  created_by,
  created_at,
  updated_at
)
VALUES
(
  '33333333-3333-4333-8333-333333333331',
  '11111111-1111-4111-8111-111111111111',
  'Atlas',
  'Drive growth analytics and campaign optimization.',
  'Marketing Operator',
  'gpt-4.1',
  '["campaign-analysis","report-generation","content-briefing"]'::jsonb,
  '["hubspot","google_analytics","mailchimp"]'::jsonb,
  '["pii-redaction","approval-for-send"]'::jsonb,
  '{"tasks_today":18,"success_rate":98.6,"avg_response_time":"1.2s","workflows_using":2}'::jsonb,
  'active',
  NULL,
  now() - interval '5 days',
  now()
),
(
  '33333333-3333-4333-8333-333333333332',
  '11111111-1111-4111-8111-111111111111',
  'Nexus',
  'Coordinate pipeline reliability and incident triage.',
  'Operations Coordinator',
  'claude-3.5-sonnet',
  '["incident-triage","workflow-health","anomaly-summary"]'::jsonb,
  '["postgres","snowflake","slack"]'::jsonb,
  '["read-only-by-default","approval-for-patches"]'::jsonb,
  '{"tasks_today":11,"success_rate":96.1,"avg_response_time":"1.7s","workflows_using":3}'::jsonb,
  'active',
  NULL,
  now() - interval '4 days',
  now()
),
(
  '33333333-3333-4333-8333-333333333333',
  '11111111-1111-4111-8111-111111111111',
  'Sentinel',
  'Monitor data quality and validation guardrails.',
  'Data Quality Agent',
  'gpt-4o-mini',
  '["schema-validation","dedupe-checks","drift-detection"]'::jsonb,
  '["mongodb","s3"]'::jsonb,
  '["strict-validation","block-on-critical-errors"]'::jsonb,
  '{"tasks_today":7,"success_rate":99.2,"avg_response_time":"2.1s","workflows_using":1}'::jsonb,
  'draft',
  NULL,
  now() - interval '3 days',
  now()
),
(
  '33333333-3333-4333-8333-333333333334',
  '11111111-1111-4111-8111-111111111111',
  'Harbor',
  'Assist support workflows and escalation routing.',
  'Support Coordinator',
  'claude-3-haiku',
  '["ticket-routing","sla-monitoring","escalation-notes"]'::jsonb,
  '["zendesk","intercom"]'::jsonb,
  '["approval-for-customer-reply"]'::jsonb,
  '{"tasks_today":0,"success_rate":0,"avg_response_time":"-","workflows_using":1}'::jsonb,
  'error',
  NULL,
  now() - interval '2 days',
  now()
)
ON CONFLICT (id) DO NOTHING;

-- 4) workflows (expected total: 3)
INSERT INTO public.workflows (
  id,
  org_id,
  name,
  description,
  status,
  environment,
  nodes,
  edges,
  config,
  created_by,
  created_at,
  updated_at
)
VALUES
(
  '44444444-4444-4444-8444-444444444441',
  '11111111-1111-4111-8111-111111111111',
  'sync-customers',
  'Synchronize customer records from CRM into core warehouse.',
  'active',
  'production',
  '[{"id":"n1","type":"source","name":"Salesforce"},{"id":"n2","type":"task","name":"Normalize"},{"id":"n3","type":"connector","name":"Postgres"}]'::jsonb,
  '[{"id":"e1","source":"n1","target":"n2"},{"id":"e2","source":"n2","target":"n3"}]'::jsonb,
  '{"schedule":"*/15 * * * *","retry":{"max":3,"backoff":"exponential"}}'::jsonb,
  NULL,
  now() - interval '6 days',
  now()
),
(
  '44444444-4444-4444-8444-444444444442',
  '11111111-1111-4111-8111-111111111111',
  'invoice-processing',
  'Extract and validate incoming invoice payloads.',
  'paused',
  'staging',
  '[{"id":"n1","type":"source","name":"Email Ingest"},{"id":"n2","type":"agent","name":"OCR Agent"},{"id":"n3","type":"approval","name":"Finance Review"}]'::jsonb,
  '[{"id":"e1","source":"n1","target":"n2"},{"id":"e2","source":"n2","target":"n3"}]'::jsonb,
  '{"schedule":"0 */2 * * *","approvalRequired":true}'::jsonb,
  NULL,
  now() - interval '5 days',
  now()
),
(
  '44444444-4444-4444-8444-444444444443',
  '11111111-1111-4111-8111-111111111111',
  'report-generation',
  'Generate and distribute weekly KPI summaries.',
  'draft',
  'production',
  '[{"id":"n1","type":"source","name":"Analytics Warehouse"},{"id":"n2","type":"task","name":"Compute KPIs"},{"id":"n3","type":"connector","name":"Slack"}]'::jsonb,
  '[{"id":"e1","source":"n1","target":"n2"},{"id":"e2","source":"n2","target":"n3"}]'::jsonb,
  '{"schedule":"0 8 * * 1","channels":["slack","email"]}'::jsonb,
  NULL,
  now() - interval '4 days',
  now()
)
ON CONFLICT (id) DO NOTHING;

-- 5) runs (expected total: 6)
INSERT INTO public.runs (
  id,
  org_id,
  workflow_id,
  workflow_name,
  status,
  trigger,
  approval_status,
  started_at,
  completed_at,
  duration_ms,
  error_message,
  metadata,
  created_at,
  updated_at
)
VALUES
(
  '55555555-5555-4555-8555-555555555551',
  '11111111-1111-4111-8111-111111111111',
  '44444444-4444-4444-8444-444444444441',
  'sync-customers',
  'completed',
  'schedule',
  'not_required',
  now() - interval '2 hours',
  now() - interval '1 hour 58 minutes',
  120000,
  NULL,
  '{"recordsProcessed":1247,"recordsFailed":0}'::jsonb,
  now() - interval '2 hours',
  now()
),
(
  '55555555-5555-4555-8555-555555555552',
  '11111111-1111-4111-8111-111111111111',
  '44444444-4444-4444-8444-444444444441',
  'sync-customers',
  'running',
  'manual',
  'not_required',
  now() - interval '12 minutes',
  NULL,
  NULL,
  NULL,
  '{"recordsProcessed":312,"etaSeconds":74}'::jsonb,
  now() - interval '12 minutes',
  now()
),
(
  '55555555-5555-4555-8555-555555555553',
  '11111111-1111-4111-8111-111111111111',
  '44444444-4444-4444-8444-444444444441',
  'sync-customers',
  'failed',
  'schedule',
  'not_required',
  now() - interval '5 hours',
  now() - interval '4 hours 57 minutes',
  180000,
  'Connection timeout while writing batch 3.',
  '{"recordsProcessed":486,"recordsFailed":19}'::jsonb,
  now() - interval '5 hours',
  now()
),
(
  '55555555-5555-4555-8555-555555555554',
  '11111111-1111-4111-8111-111111111111',
  '44444444-4444-4444-8444-444444444442',
  'invoice-processing',
  'pending',
  'schedule',
  'pending',
  NULL,
  NULL,
  NULL,
  NULL,
  '{"queuePosition":2}'::jsonb,
  now() - interval '25 minutes',
  now()
),
(
  '55555555-5555-4555-8555-555555555555',
  '11111111-1111-4111-8111-111111111111',
  '44444444-4444-4444-8444-444444444442',
  'invoice-processing',
  'pending',
  'manual',
  'pending',
  NULL,
  NULL,
  NULL,
  NULL,
  '{"queuePosition":5}'::jsonb,
  now() - interval '45 minutes',
  now()
),
(
  '55555555-5555-4555-8555-555555555556',
  '11111111-1111-4111-8111-111111111111',
  '44444444-4444-4444-8444-444444444443',
  'report-generation',
  'cancelled',
  'manual',
  'rejected',
  now() - interval '1 day',
  now() - interval '23 hours 55 minutes',
  300000,
  'Cancelled after review rejection.',
  '{"cancelledBy":"reviewer","reason":"insufficient data quality"}'::jsonb,
  now() - interval '1 day',
  now()
)
ON CONFLICT (id) DO NOTHING;

-- 6) run_steps (optional detail rows; keeps relationships valid)
INSERT INTO public.run_steps (
  id,
  org_id,
  run_id,
  name,
  status,
  order_index,
  started_at,
  completed_at,
  duration_ms,
  logs,
  metadata,
  created_at,
  updated_at
)
VALUES
(
  '66666666-6666-4666-8666-666666666661',
  '11111111-1111-4111-8111-111111111111',
  '55555555-5555-4555-8555-555555555551',
  'Fetch records',
  'completed',
  0,
  now() - interval '2 hours',
  now() - interval '1 hour 59 minutes',
  60000,
  ARRAY['Fetched 1247 records'],
  '{}'::jsonb,
  now() - interval '2 hours',
  now()
),
(
  '66666666-6666-4666-8666-666666666662',
  '11111111-1111-4111-8111-111111111111',
  '55555555-5555-4555-8555-555555555551',
  'Load destination',
  'completed',
  1,
  now() - interval '1 hour 59 minutes',
  now() - interval '1 hour 58 minutes',
  60000,
  ARRAY['Load complete'],
  '{}'::jsonb,
  now() - interval '2 hours',
  now()
),
(
  '66666666-6666-4666-8666-666666666663',
  '11111111-1111-4111-8111-111111111111',
  '55555555-5555-4555-8555-555555555552',
  'Fetch records',
  'running',
  0,
  now() - interval '12 minutes',
  NULL,
  NULL,
  ARRAY['Streaming data from CRM'],
  '{"progress":0.35}'::jsonb,
  now() - interval '12 minutes',
  now()
),
(
  '66666666-6666-4666-8666-666666666664',
  '11111111-1111-4111-8111-111111111111',
  '55555555-5555-4555-8555-555555555553',
  'Load destination',
  'failed',
  1,
  now() - interval '4 hours 59 minutes',
  now() - interval '4 hours 57 minutes',
  120000,
  ARRAY['Timeout on batch 3'],
  '{"batch":3}'::jsonb,
  now() - interval '5 hours',
  now()
)
ON CONFLICT (id) DO NOTHING;

-- 7) approvals (expected total: 2)
INSERT INTO public.approvals (
  id,
  org_id,
  run_id,
  title,
  description,
  type,
  priority,
  status,
  requested_by,
  reviewed_by,
  requested_at,
  reviewed_at,
  context,
  created_at,
  updated_at
)
VALUES
(
  '77777777-7777-4777-8777-777777777771',
  '11111111-1111-4111-8111-111111111111',
  '55555555-5555-4555-8555-555555555554',
  'Approve invoice-processing run',
  'Run requires manual approval before execution.',
  'workflow',
  'high',
  'pending',
  'operator@gravitre.ai',
  NULL,
  now() - interval '20 minutes',
  NULL,
  '{"entity":"invoice-processing","action":"approve-run","impact":"unblocks queue"}'::jsonb,
  now() - interval '20 minutes',
  now()
),
(
  '77777777-7777-4777-8777-777777777772',
  '11111111-1111-4111-8111-111111111111',
  '55555555-5555-4555-8555-555555555555',
  'Review data retention update',
  'Confirm policy update before queued execution.',
  'config',
  'medium',
  'pending',
  'operator@gravitre.ai',
  NULL,
  now() - interval '40 minutes',
  NULL,
  '{"entity":"retention-policy","action":"approve-change"}'::jsonb,
  now() - interval '40 minutes',
  now()
)
ON CONFLICT (id) DO NOTHING;

-- 8) connected_systems (expected total: 4)
INSERT INTO public.connected_systems (
  id,
  org_id,
  system_key,
  name,
  type,
  status,
  config,
  last_synced_at,
  created_at,
  updated_at
)
VALUES
(
  '88888888-8888-4888-8888-888888888881',
  '11111111-1111-4111-8111-111111111111',
  'salesforce',
  'Salesforce CRM',
  'crm',
  'connected',
  '{"region":"us-east-1","version":"v60"}'::jsonb,
  now() - interval '5 minutes',
  now() - interval '6 days',
  now()
),
(
  '88888888-8888-4888-8888-888888888882',
  '11111111-1111-4111-8111-111111111111',
  'postgres_primary',
  'Postgres Primary',
  'database',
  'connected',
  '{"schema":"public","ssl":true}'::jsonb,
  now() - interval '2 minutes',
  now() - interval '6 days',
  now()
),
(
  '88888888-8888-4888-8888-888888888883',
  '11111111-1111-4111-8111-111111111111',
  'snowflake_dw',
  'Snowflake Warehouse',
  'warehouse',
  'connected',
  '{"warehouse":"COMPUTE_XS","database":"GRAVITRE"}'::jsonb,
  now() - interval '12 minutes',
  now() - interval '6 days',
  now()
),
(
  '88888888-8888-4888-8888-888888888884',
  '11111111-1111-4111-8111-111111111111',
  'zendesk',
  'Zendesk',
  'support',
  'error',
  '{"error":"token_expired"}'::jsonb,
  now() - interval '1 day',
  now() - interval '6 days',
  now()
)
ON CONFLICT (id) DO NOTHING;

-- 9) model_settings (expected total: 1)
INSERT INTO public.model_settings (
  id,
  org_id,
  workspace_model,
  operator_model,
  agent_default_model,
  fallback_model,
  allow_overrides,
  show_model_in_logs,
  created_at,
  updated_at
)
VALUES (
  '99999999-9999-4999-8999-999999999991',
  '11111111-1111-4111-8111-111111111111',
  'auto',
  'gpt-4.1',
  'balanced',
  'fast',
  true,
  true,
  now() - interval '6 days',
  now()
)
ON CONFLICT (org_id) DO NOTHING;

-- 10) normalize seeded data to demo org context used by API fallback
-- Keeps this script idempotent and aligns seeded rows with:
-- 00000000-0000-0000-0000-000000000001
INSERT INTO public.organizations (
  id,
  name,
  slug,
  settings,
  status,
  created_at,
  updated_at
)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'Gravitre Demo',
  'gravitre-demo',
  '{"theme":"dark","timezone":"UTC","locale":"en-US"}'::jsonb,
  'active',
  now() - interval '7 days',
  now()
)
ON CONFLICT (id) DO NOTHING;

UPDATE public.users
SET org_id = '00000000-0000-0000-0000-000000000001'
WHERE org_id = '11111111-1111-4111-8111-111111111111';

UPDATE public.organization_members
SET org_id = '00000000-0000-0000-0000-000000000001'
WHERE org_id = '11111111-1111-4111-8111-111111111111';

UPDATE public.agents
SET org_id = '00000000-0000-0000-0000-000000000001'
WHERE org_id = '11111111-1111-4111-8111-111111111111';

UPDATE public.workflows
SET org_id = '00000000-0000-0000-0000-000000000001'
WHERE org_id = '11111111-1111-4111-8111-111111111111';

UPDATE public.runs
SET org_id = '00000000-0000-0000-0000-000000000001'
WHERE org_id = '11111111-1111-4111-8111-111111111111';

UPDATE public.run_steps
SET org_id = '00000000-0000-0000-0000-000000000001'
WHERE org_id = '11111111-1111-4111-8111-111111111111';

UPDATE public.approvals
SET org_id = '00000000-0000-0000-0000-000000000001'
WHERE org_id = '11111111-1111-4111-8111-111111111111';

UPDATE public.connected_systems
SET org_id = '00000000-0000-0000-0000-000000000001'
WHERE org_id = '11111111-1111-4111-8111-111111111111';

UPDATE public.api_keys
SET org_id = '00000000-0000-0000-0000-000000000001'
WHERE org_id = '11111111-1111-4111-8111-111111111111';

UPDATE public.webhooks
SET org_id = '00000000-0000-0000-0000-000000000001'
WHERE org_id = '11111111-1111-4111-8111-111111111111';

UPDATE public.audit_logs
SET org_id = '00000000-0000-0000-0000-000000000001'
WHERE org_id = '11111111-1111-4111-8111-111111111111';

UPDATE public.model_settings
SET org_id = '00000000-0000-0000-0000-000000000001'
WHERE org_id = '11111111-1111-4111-8111-111111111111';

-- ============================================================
-- Gravitre Cohesive Demo Seed (Org 2)
-- ============================================================
-- Secondary demo organization so UI/API can toggle between orgs.
-- Target org:
--   11111111-1111-4111-8111-111111111111
-- Suggested toggle:
--   /api/... ?org_id=11111111-1111-4111-8111-111111111111

-- ------------------------------------------------------------
-- 1) Organization
-- ------------------------------------------------------------
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
  '{
    "environment":"production",
    "industry":"AI Automation",
    "timezone":"America/New_York",
    "defaultCurrency":"USD",
    "notificationPreferences":{"slack":true,"email":true,"digest":"daily"},
    "aiRouting":{"mode":"quality","costMode":"balanced"},
    "safety":{"requireApprovalsForExternalComms":true,"piiRedaction":true}
  }'::jsonb,
  'active',
  now() - interval '120 days',
  now()
)
ON CONFLICT (id) DO UPDATE
SET
  name = EXCLUDED.name,
  slug = EXCLUDED.slug,
  settings = EXCLUDED.settings,
  status = EXCLUDED.status,
  updated_at = now();

-- ------------------------------------------------------------
-- 2) Users
-- ------------------------------------------------------------
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
  now() - interval '110 days',
  now()
)
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  email = EXCLUDED.email,
  full_name = EXCLUDED.full_name,
  role = EXCLUDED.role,
  status = EXCLUDED.status,
  updated_at = now();

-- ------------------------------------------------------------
-- 3) Agents
-- ------------------------------------------------------------
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
  '32000000-0000-4000-8000-000000000001',
  '11111111-1111-4111-8111-111111111111',
  'Revenue Ops Agent',
  'Improves lead routing quality and pipeline throughput.',
  'Revenue Operations',
  'gpt-4.1',
  '["lead-scoring","routing","pipeline-health"]'::jsonb,
  '["hubspot","salesforce","slack","stripe"]'::jsonb,
  '["approval-for-high-risk-segments"]'::jsonb,
  '{"type":"ops","kpiFocus":["conversion","velocity"]}'::jsonb,
  'active',
  NULL,
  now() - interval '90 days',
  now()
),
(
  '32000000-0000-4000-8000-000000000002',
  '11111111-1111-4111-8111-111111111111',
  'Customer Support Agent',
  'Triage support requests and draft compliant responses.',
  'Support Operations',
  'claude-3.5-sonnet',
  '["ticket-prioritization","drafting","sentiment-check"]'::jsonb,
  '["zendesk","gmail","slack"]'::jsonb,
  '["require-human-approval-for-vip"]'::jsonb,
  '{"type":"support","slaTargetMinutes":30}'::jsonb,
  'active',
  NULL,
  now() - interval '88 days',
  now()
),
(
  '32000000-0000-4000-8000-000000000003',
  '11111111-1111-4111-8111-111111111111',
  'Lifecycle Marketing Agent',
  'Builds segmented lifecycle messaging and campaign summaries.',
  'Marketing',
  'gpt-4o',
  '["campaign-segmentation","copy-optimization","reporting"]'::jsonb,
  '["hubspot","gmail","notion"]'::jsonb,
  '["approval-before-send"]'::jsonb,
  '{"type":"marketing","cadence":"weekly"}'::jsonb,
  'active',
  NULL,
  now() - interval '86 days',
  now()
),
(
  '32000000-0000-4000-8000-000000000004',
  '11111111-1111-4111-8111-111111111111',
  'Reporting Analyst Agent',
  'Assembles executive reports from billing and pipeline sources.',
  'Analytics',
  'claude-3-opus',
  '["kpi-reporting","trend-analysis","executive-summary"]'::jsonb,
  '["stripe","salesforce","google_drive","notion"]'::jsonb,
  '["approval-before-external-delivery"]'::jsonb,
  '{"type":"analytics","reportWindow":"weekly"}'::jsonb,
  'active',
  NULL,
  now() - interval '84 days',
  now()
)
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  name = EXCLUDED.name,
  purpose = EXCLUDED.purpose,
  role = EXCLUDED.role,
  model = EXCLUDED.model,
  capabilities = EXCLUDED.capabilities,
  systems = EXCLUDED.systems,
  guardrails = EXCLUDED.guardrails,
  config = EXCLUDED.config,
  status = EXCLUDED.status,
  updated_at = now();

-- ------------------------------------------------------------
-- 4) Connected Systems
-- ------------------------------------------------------------
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
('42000000-0000-4000-8000-000000000001','11111111-1111-4111-8111-111111111111','hubspot','HubSpot CRM','crm','connected','{"vendor":"hubspot","connectedAt":"2026-02-01T09:00:00Z"}'::jsonb,now() - interval '12 minutes',now() - interval '80 days',now()),
('42000000-0000-4000-8000-000000000002','11111111-1111-4111-8111-111111111111','salesforce','Salesforce','crm','connected','{"vendor":"salesforce","connectedAt":"2026-02-01T10:00:00Z"}'::jsonb,now() - interval '20 minutes',now() - interval '80 days',now()),
('42000000-0000-4000-8000-000000000003','11111111-1111-4111-8111-111111111111','slack','Slack','communication','connected','{"vendor":"slack","defaultChannel":"#ops"}'::jsonb,now() - interval '6 minutes',now() - interval '79 days',now()),
('42000000-0000-4000-8000-000000000004','11111111-1111-4111-8111-111111111111','google_drive','Google Drive','storage','connected','{"vendor":"google","folder":"Ops Reports"}'::jsonb,now() - interval '28 minutes',now() - interval '79 days',now()),
('42000000-0000-4000-8000-000000000005','11111111-1111-4111-8111-111111111111','zendesk','Zendesk','support','error','{"vendor":"zendesk","error":"rate_limit"}'::jsonb,now() - interval '4 hours',now() - interval '78 days',now()),
('42000000-0000-4000-8000-000000000006','11111111-1111-4111-8111-111111111111','stripe','Stripe','billing','connected','{"vendor":"stripe","mode":"live"}'::jsonb,now() - interval '14 minutes',now() - interval '78 days',now()),
('42000000-0000-4000-8000-000000000007','11111111-1111-4111-8111-111111111111','gmail','Gmail','email','connected','{"vendor":"google","sender":"ops@gravitre.ai"}'::jsonb,now() - interval '35 minutes',now() - interval '77 days',now()),
('42000000-0000-4000-8000-000000000008','11111111-1111-4111-8111-111111111111','notion','Notion','knowledge','connected','{"vendor":"notion","workspace":"Gravitre Ops"}'::jsonb,now() - interval '82 minutes',now() - interval '77 days',now()),
('42000000-0000-4000-8000-000000000009','11111111-1111-4111-8111-111111111111','github','GitHub','engineering','pending','{"vendor":"github","statusNote":"awaiting permission"}'::jsonb,now() - interval '8 hours',now() - interval '76 days',now())
ON CONFLICT (org_id, system_key) DO UPDATE
SET
  name = EXCLUDED.name,
  type = EXCLUDED.type,
  status = EXCLUDED.status,
  config = EXCLUDED.config,
  last_synced_at = EXCLUDED.last_synced_at,
  updated_at = now();

-- ------------------------------------------------------------
-- 5) Workflows
-- ------------------------------------------------------------
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
  '52000000-0000-4000-8000-000000000001',
  '11111111-1111-4111-8111-111111111111',
  'Lead Qualification & Routing',
  'Scores inbound leads and syncs qualified opportunities.',
  'active',
  'production',
  '[{"id":"n1","type":"source","name":"HubSpot Intake"},{"id":"n2","type":"agent","name":"Revenue Ops Agent"},{"id":"n3","type":"connector","name":"Salesforce Sync"}]'::jsonb,
  '[{"id":"e1","source":"n1","target":"n2"},{"id":"e2","source":"n2","target":"n3"}]'::jsonb,
  '{"trigger_type":"webhook","trigger_config":{"source":"hubspot.form"},"version":2}'::jsonb,
  NULL,
  now() - interval '70 days',
  now()
),
(
  '52000000-0000-4000-8000-000000000002',
  '11111111-1111-4111-8111-111111111111',
  'Customer Escalation Triage',
  'Prioritizes and routes high-risk support cases.',
  'active',
  'production',
  '[{"id":"n1","type":"source","name":"Zendesk Ticket"},{"id":"n2","type":"agent","name":"Customer Support Agent"},{"id":"n3","type":"approval","name":"Compliance Check"}]'::jsonb,
  '[{"id":"e1","source":"n1","target":"n2"},{"id":"e2","source":"n2","target":"n3"}]'::jsonb,
  '{"trigger_type":"event","trigger_config":{"event":"ticket_escalated"},"version":2}'::jsonb,
  NULL,
  now() - interval '69 days',
  now()
),
(
  '52000000-0000-4000-8000-000000000003',
  '11111111-1111-4111-8111-111111111111',
  'Weekly Executive Revenue Report',
  'Generates and publishes weekly revenue summary.',
  'active',
  'production',
  '[{"id":"n1","type":"source","name":"Stripe Data"},{"id":"n2","type":"agent","name":"Reporting Analyst Agent"},{"id":"n3","type":"connector","name":"Google Drive Export"}]'::jsonb,
  '[{"id":"e1","source":"n1","target":"n2"},{"id":"e2","source":"n2","target":"n3"}]'::jsonb,
  '{"trigger_type":"schedule","trigger_config":{"cron":"0 8 * * 1"},"version":3}'::jsonb,
  NULL,
  now() - interval '68 days',
  now()
),
(
  '52000000-0000-4000-8000-000000000004',
  '11111111-1111-4111-8111-111111111111',
  'Campaign Performance Summary',
  'Builds campaign summary digest for GTM leadership.',
  'active',
  'production',
  '[{"id":"n1","type":"source","name":"HubSpot Campaigns"},{"id":"n2","type":"agent","name":"Lifecycle Marketing Agent"},{"id":"n3","type":"connector","name":"Notion Digest"}]'::jsonb,
  '[{"id":"e1","source":"n1","target":"n2"},{"id":"e2","source":"n2","target":"n3"}]'::jsonb,
  '{"trigger_type":"schedule","trigger_config":{"cron":"0 10 * * 5"},"version":2}'::jsonb,
  NULL,
  now() - interval '67 days',
  now()
)
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  status = EXCLUDED.status,
  environment = EXCLUDED.environment,
  nodes = EXCLUDED.nodes,
  edges = EXCLUDED.edges,
  config = EXCLUDED.config,
  updated_at = now();

-- ------------------------------------------------------------
-- 6) Runs + Approvals visibility
-- ------------------------------------------------------------
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
('62000000-0000-4000-8000-000000000001','11111111-1111-4111-8111-111111111111','52000000-0000-4000-8000-000000000001','Lead Qualification & Routing','completed','webhook','not_required',now() - interval '3 hours',now() - interval '2 hours 58 minutes',120000,NULL,'{"leadsProcessed":98}'::jsonb,now() - interval '3 hours',now()),
('62000000-0000-4000-8000-000000000002','11111111-1111-4111-8111-111111111111','52000000-0000-4000-8000-000000000002','Customer Escalation Triage','running','event','not_required',now() - interval '14 minutes',NULL,NULL,NULL,'{"ticketsInFlight":3}'::jsonb,now() - interval '14 minutes',now()),
('62000000-0000-4000-8000-000000000003','11111111-1111-4111-8111-111111111111','52000000-0000-4000-8000-000000000003','Weekly Executive Revenue Report','pending','schedule','pending',NULL,NULL,NULL,NULL,'{"queuePosition":2}'::jsonb,now() - interval '18 minutes',now()),
('62000000-0000-4000-8000-000000000004','11111111-1111-4111-8111-111111111111','52000000-0000-4000-8000-000000000004','Campaign Performance Summary','failed','schedule','not_required',now() - interval '6 hours',now() - interval '5 hours 53 minutes',420000,'Notion connector timeout','{"failedConnector":"notion"}'::jsonb,now() - interval '6 hours',now()),
('62000000-0000-4000-8000-000000000005','11111111-1111-4111-8111-111111111111','52000000-0000-4000-8000-000000000002','Customer Escalation Triage','completed','event','approved',now() - interval '1 day',now() - interval '23 hours 45 minutes',900000,NULL,'{"vipCases":2}'::jsonb,now() - interval '1 day',now())
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  workflow_id = EXCLUDED.workflow_id,
  workflow_name = EXCLUDED.workflow_name,
  status = EXCLUDED.status,
  trigger = EXCLUDED.trigger,
  approval_status = EXCLUDED.approval_status,
  started_at = EXCLUDED.started_at,
  completed_at = EXCLUDED.completed_at,
  duration_ms = EXCLUDED.duration_ms,
  error_message = EXCLUDED.error_message,
  metadata = EXCLUDED.metadata,
  updated_at = now();

INSERT INTO public.approvals (
  id, org_id, run_id, title, description, type, priority, status, requested_by, reviewed_by, requested_at, reviewed_at, context, created_at, updated_at
)
VALUES
('72000000-0000-4000-8000-000000000001','11111111-1111-4111-8111-111111111111','62000000-0000-4000-8000-000000000003','Approve weekly revenue report delivery','Executive report pending owner signoff.','workflow','high','pending','Reporting Analyst Agent',NULL,now() - interval '20 minutes',NULL,'{"distribution":"leadership@gravitre.ai"}'::jsonb,now() - interval '20 minutes',now()),
('72000000-0000-4000-8000-000000000002','11111111-1111-4111-8111-111111111111','62000000-0000-4000-8000-000000000002','Approve VIP escalation reply','VIP escalation message needs compliance check.','workflow','high','pending','Customer Support Agent',NULL,now() - interval '12 minutes',NULL,'{"risk":"medium"}'::jsonb,now() - interval '12 minutes',now())
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  run_id = EXCLUDED.run_id,
  title = EXCLUDED.title,
  description = EXCLUDED.description,
  type = EXCLUDED.type,
  priority = EXCLUDED.priority,
  status = EXCLUDED.status,
  requested_by = EXCLUDED.requested_by,
  reviewed_by = EXCLUDED.reviewed_by,
  requested_at = EXCLUDED.requested_at,
  reviewed_at = EXCLUDED.reviewed_at,
  context = EXCLUDED.context,
  updated_at = now();

-- ------------------------------------------------------------
-- 7) Goals / Plans
-- ------------------------------------------------------------
INSERT INTO public.goals (
  id, org_id, objective, category, priority, frequency, department, success_metrics, connected_systems, status, created_at, updated_at
)
VALUES
('82000000-0000-4000-8000-000000000001','11111111-1111-4111-8111-111111111111','Increase SQL conversion by 10%','revenue','high','weekly','Revenue Ops','{"target":10,"progress":6}'::jsonb,ARRAY['hubspot','salesforce'],'active',now() - interval '40 days',now()),
('82000000-0000-4000-8000-000000000002','11111111-1111-4111-8111-111111111111','Reduce escalation response time by 25%','support','high','daily','Support','{"target":25,"progress":14}'::jsonb,ARRAY['zendesk','gmail','slack'],'active',now() - interval '38 days',now())
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  objective = EXCLUDED.objective,
  category = EXCLUDED.category,
  priority = EXCLUDED.priority,
  frequency = EXCLUDED.frequency,
  department = EXCLUDED.department,
  success_metrics = EXCLUDED.success_metrics,
  connected_systems = EXCLUDED.connected_systems,
  status = EXCLUDED.status,
  updated_at = now();

INSERT INTO public.goal_plans (
  id, org_id, goal_id, proposed_steps, required_connectors, required_agents, approval_gates, estimated_impact, created_at, updated_at
)
VALUES
('83000000-0000-4000-8000-000000000001','11111111-1111-4111-8111-111111111111','82000000-0000-4000-8000-000000000001','[{"step":"retrain scoring model"},{"step":"route by intent"}]'::jsonb,ARRAY['hubspot','salesforce'],ARRAY['32000000-0000-4000-8000-000000000001'::uuid],'[{"gate":"routing-policy","approverRole":"owner"}]'::jsonb,'{"expectedLift":"10%","confidence":0.76}'::jsonb,now() - interval '36 days',now()),
('83000000-0000-4000-8000-000000000002','11111111-1111-4111-8111-111111111111','82000000-0000-4000-8000-000000000002','[{"step":"priority triage"},{"step":"approval checks for VIP"}]'::jsonb,ARRAY['zendesk','gmail'],ARRAY['32000000-0000-4000-8000-000000000002'::uuid],'[{"gate":"vip-send","approverRole":"admin"}]'::jsonb,'{"expectedLift":"25%","confidence":0.72}'::jsonb,now() - interval '35 days',now())
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  goal_id = EXCLUDED.goal_id,
  proposed_steps = EXCLUDED.proposed_steps,
  required_connectors = EXCLUDED.required_connectors,
  required_agents = EXCLUDED.required_agents,
  approval_gates = EXCLUDED.approval_gates,
  estimated_impact = EXCLUDED.estimated_impact,
  updated_at = now();

-- ------------------------------------------------------------
-- 8) Model settings (safe upsert)
-- ------------------------------------------------------------
UPDATE public.model_settings
SET
  workspace_model = 'gpt-4.1',
  operator_model = 'claude-3.5-sonnet',
  agent_default_model = 'balanced',
  fallback_model = 'fast',
  allow_overrides = true,
  show_model_in_logs = true,
  updated_at = now()
WHERE org_id = '11111111-1111-4111-8111-111111111111';

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
SELECT
  '99999999-9999-4999-8999-999999999992',
  '11111111-1111-4111-8111-111111111111',
  'gpt-4.1',
  'claude-3.5-sonnet',
  'balanced',
  'fast',
  true,
  true,
  now() - interval '50 days',
  now()
WHERE NOT EXISTS (
  SELECT 1
  FROM public.model_settings
  WHERE org_id = '11111111-1111-4111-8111-111111111111'
)
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  workspace_model = EXCLUDED.workspace_model,
  operator_model = EXCLUDED.operator_model,
  agent_default_model = EXCLUDED.agent_default_model,
  fallback_model = EXCLUDED.fallback_model,
  allow_overrides = EXCLUDED.allow_overrides,
  show_model_in_logs = EXCLUDED.show_model_in_logs,
  updated_at = now();

-- ============================================================
-- Gravitre Cohesive Demo Seed (Acme Corp)
-- ============================================================
-- Idempotent, non-destructive seed script for a unified product demo.
-- All org-scoped demo rows use:
--   00000000-0000-0000-0000-000000000001

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
  '00000000-0000-0000-0000-000000000001',
  'Acme Corp',
  'acme-corp',
  '{
    "environment":"production",
    "industry":"B2B SaaS",
    "timezone":"America/Los_Angeles",
    "defaultCurrency":"USD",
    "notificationPreferences":{"slack":true,"email":true,"digest":"daily"},
    "aiRouting":{"mode":"balanced","costMode":"optimized"},
    "safety":{"requireApprovalsForExternalComms":true,"piiRedaction":true}
  }'::jsonb,
  'active',
  now() - interval '90 days',
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
-- 2) Users / Organization Members
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
  '20000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  NULL,
  'jordan.ortiz@acmecorp.com',
  'Jordan Ortiz',
  'owner',
  'active',
  now() - interval '80 days',
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

-- Create org membership when matching auth user exists.
INSERT INTO public.organization_members (
  id,
  org_id,
  user_id,
  role,
  created_at
)
SELECT
  '21000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  au.id,
  'owner',
  now() - interval '80 days'
FROM auth.users au
WHERE lower(au.email) = 'jordan.ortiz@acmecorp.com'
ON CONFLICT (org_id, user_id) DO UPDATE
SET role = EXCLUDED.role;

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
  '30000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'Revenue Ops Agent',
  'Optimizes lead routing and opportunity progression.',
  'Revenue Operations',
  'gpt-4.1',
  '["lead-scoring","routing","pipeline-health"]'::jsonb,
  '["hubspot","salesforce","slack","stripe"]'::jsonb,
  '["approval-for-high-value-actions"]'::jsonb,
  '{"type":"ops","kpiFocus":["mql_to_sql","pipeline_velocity"],"temperature":0.2}'::jsonb,
  'active',
  NULL,
  now() - interval '60 days',
  now()
),
(
  '30000000-0000-4000-8000-000000000002',
  '00000000-0000-0000-0000-000000000001',
  'Customer Support Agent',
  'Triage escalations and draft customer-safe responses.',
  'Support Operations',
  'claude-3.5-sonnet',
  '["ticket-triage","response-drafting","sentiment-analysis"]'::jsonb,
  '["zendesk","slack","gmail"]'::jsonb,
  '["require-human-approval-for-vip"]'::jsonb,
  '{"type":"support","slaTargetMinutes":45}'::jsonb,
  'active',
  NULL,
  now() - interval '58 days',
  now()
),
(
  '30000000-0000-4000-8000-000000000003',
  '00000000-0000-0000-0000-000000000001',
  'Lifecycle Marketing Agent',
  'Automates campaigns and lifecycle journeys.',
  'Marketing',
  'gpt-4o',
  '["campaign-orchestration","copy-generation","audience-segmentation"]'::jsonb,
  '["hubspot","gmail","notion","slack"]'::jsonb,
  '["approval-before-send"]'::jsonb,
  '{"type":"marketing","channelMix":["email","slack"],"cadence":"weekly"}'::jsonb,
  'active',
  NULL,
  now() - interval '57 days',
  now()
),
(
  '30000000-0000-4000-8000-000000000004',
  '00000000-0000-0000-0000-000000000001',
  'Data Quality Agent',
  'Validates records and prevents bad syncs.',
  'Data Platform',
  'gpt-4o-mini',
  '["schema-validation","dedupe","anomaly-detection"]'::jsonb,
  '["salesforce","hubspot","google-drive"]'::jsonb,
  '["block-on-critical-errors"]'::jsonb,
  '{"type":"quality","confidenceThreshold":0.85}'::jsonb,
  'active',
  NULL,
  now() - interval '56 days',
  now()
),
(
  '30000000-0000-4000-8000-000000000005',
  '00000000-0000-0000-0000-000000000001',
  'Reporting Analyst Agent',
  'Produces weekly executive scorecards and insights.',
  'Analytics',
  'claude-3-opus',
  '["kpi-reporting","executive-summary","trend-analysis"]'::jsonb,
  '["stripe","salesforce","google-drive","notion"]'::jsonb,
  '["approval-before-external-delivery"]'::jsonb,
  '{"type":"analytics","reportWindow":"weekly"}'::jsonb,
  'active',
  NULL,
  now() - interval '54 days',
  now()
),
(
  '30000000-0000-4000-8000-000000000006',
  '00000000-0000-0000-0000-000000000001',
  'Compliance Review Agent',
  'Reviews policy risk before customer-facing actions.',
  'Risk & Compliance',
  'gpt-4.1-mini',
  '["policy-checks","risk-scoring","approval-routing"]'::jsonb,
  '["notion","github","slack","gmail"]'::jsonb,
  '["always-require-human-override-on-high-risk"]'::jsonb,
  '{"type":"compliance","riskTolerance":"low"}'::jsonb,
  'active',
  NULL,
  now() - interval '53 days',
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
('40000000-0000-4000-8000-000000000001','00000000-0000-0000-0000-000000000001','hubspot','HubSpot CRM','crm','connected','{"vendor":"hubspot","connectedAt":"2026-03-01T09:00:00Z","owner":"Revenue Ops"}'::jsonb,now() - interval '8 minutes',now() - interval '55 days',now()),
('40000000-0000-4000-8000-000000000002','00000000-0000-0000-0000-000000000001','salesforce','Salesforce','crm','connected','{"vendor":"salesforce","connectedAt":"2026-03-02T10:00:00Z","owner":"Revenue Ops"}'::jsonb,now() - interval '16 minutes',now() - interval '54 days',now()),
('40000000-0000-4000-8000-000000000003','00000000-0000-0000-0000-000000000001','slack','Slack','communication','connected','{"vendor":"slack","connectedAt":"2026-03-02T13:00:00Z","defaultChannel":"#ops-alerts"}'::jsonb,now() - interval '4 minutes',now() - interval '54 days',now()),
('40000000-0000-4000-8000-000000000004','00000000-0000-0000-0000-000000000001','google_drive','Google Drive','storage','connected','{"vendor":"google","connectedAt":"2026-03-03T08:00:00Z","folder":"Executive Reports"}'::jsonb,now() - interval '32 minutes',now() - interval '53 days',now()),
('40000000-0000-4000-8000-000000000005','00000000-0000-0000-0000-000000000001','zendesk','Zendesk','support','error','{"vendor":"zendesk","connectedAt":"2026-03-03T09:00:00Z","error":"oauth_token_expired"}'::jsonb,now() - interval '3 hours',now() - interval '53 days',now()),
('40000000-0000-4000-8000-000000000006','00000000-0000-0000-0000-000000000001','stripe','Stripe','billing','connected','{"vendor":"stripe","connectedAt":"2026-03-03T11:00:00Z","mode":"live"}'::jsonb,now() - interval '10 minutes',now() - interval '53 days',now()),
('40000000-0000-4000-8000-000000000007','00000000-0000-0000-0000-000000000001','gmail','Gmail','email','connected','{"vendor":"google","connectedAt":"2026-03-04T09:00:00Z","sender":"ops@acmecorp.com"}'::jsonb,now() - interval '22 minutes',now() - interval '52 days',now()),
('40000000-0000-4000-8000-000000000008','00000000-0000-0000-0000-000000000001','notion','Notion','knowledge','connected','{"vendor":"notion","connectedAt":"2026-03-04T13:00:00Z","workspace":"Acme GTM"}'::jsonb,now() - interval '70 minutes',now() - interval '52 days',now()),
('40000000-0000-4000-8000-000000000009','00000000-0000-0000-0000-000000000001','github','GitHub','engineering','pending','{"vendor":"github","connectedAt":"2026-03-05T10:00:00Z","statusNote":"awaiting app approval"}'::jsonb,now() - interval '6 hours',now() - interval '51 days',now())
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
  '50000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'Lead Qualification & Routing',
  'Scores inbound leads and routes high-intent leads to the right account owner.',
  'active',
  'production',
  '[{"id":"n1","type":"source","name":"HubSpot Intake"},{"id":"n2","type":"agent","name":"Revenue Ops Agent"},{"id":"n3","type":"decision","name":"Score Gate"},{"id":"n4","type":"connector","name":"Salesforce Update"},{"id":"n5","type":"connector","name":"Slack Alert"}]'::jsonb,
  '[{"id":"e1","source":"n1","target":"n2"},{"id":"e2","source":"n2","target":"n3"},{"id":"e3","source":"n3","target":"n4"},{"id":"e4","source":"n3","target":"n5"}]'::jsonb,
  '{"trigger_type":"webhook","trigger_config":{"source":"hubspot.form_submission"},"version":3}'::jsonb,
  NULL,
  now() - interval '45 days',
  now()
),
(
  '50000000-0000-4000-8000-000000000002',
  '00000000-0000-0000-0000-000000000001',
  'Customer Escalation Triage',
  'Triage high-priority support escalations and prepare response drafts.',
  'active',
  'production',
  '[{"id":"n1","type":"source","name":"Zendesk Ticket"},{"id":"n2","type":"agent","name":"Customer Support Agent"},{"id":"n3","type":"approval","name":"Compliance Review"},{"id":"n4","type":"connector","name":"Gmail Draft"}]'::jsonb,
  '[{"id":"e1","source":"n1","target":"n2"},{"id":"e2","source":"n2","target":"n3"},{"id":"e3","source":"n3","target":"n4"}]'::jsonb,
  '{"trigger_type":"event","trigger_config":{"event":"ticket_escalated"},"version":2}'::jsonb,
  NULL,
  now() - interval '43 days',
  now()
),
(
  '50000000-0000-4000-8000-000000000003',
  '00000000-0000-0000-0000-000000000001',
  'Weekly Executive Revenue Report',
  'Builds executive-level revenue report with pipeline, bookings, and churn highlights.',
  'active',
  'production',
  '[{"id":"n1","type":"source","name":"Stripe Revenue"},{"id":"n2","type":"source","name":"Salesforce Pipeline"},{"id":"n3","type":"agent","name":"Reporting Analyst Agent"},{"id":"n4","type":"approval","name":"Exec Approval"},{"id":"n5","type":"connector","name":"Google Drive Export"}]'::jsonb,
  '[{"id":"e1","source":"n1","target":"n3"},{"id":"e2","source":"n2","target":"n3"},{"id":"e3","source":"n3","target":"n4"},{"id":"e4","source":"n4","target":"n5"}]'::jsonb,
  '{"trigger_type":"schedule","trigger_config":{"cron":"0 8 * * 1"},"version":4}'::jsonb,
  NULL,
  now() - interval '41 days',
  now()
),
(
  '50000000-0000-4000-8000-000000000004',
  '00000000-0000-0000-0000-000000000001',
  'Churn Risk Detection',
  'Flags accounts with declining engagement and payment risk signals.',
  'active',
  'production',
  '[{"id":"n1","type":"source","name":"Product Usage Feed"},{"id":"n2","type":"source","name":"Stripe Billing"},{"id":"n3","type":"agent","name":"Data Quality Agent"},{"id":"n4","type":"agent","name":"Revenue Ops Agent"},{"id":"n5","type":"connector","name":"Slack Alert"}]'::jsonb,
  '[{"id":"e1","source":"n1","target":"n3"},{"id":"e2","source":"n2","target":"n3"},{"id":"e3","source":"n3","target":"n4"},{"id":"e4","source":"n4","target":"n5"}]'::jsonb,
  '{"trigger_type":"schedule","trigger_config":{"cron":"0 */6 * * *"},"version":2}'::jsonb,
  NULL,
  now() - interval '38 days',
  now()
),
(
  '50000000-0000-4000-8000-000000000005',
  '00000000-0000-0000-0000-000000000001',
  'Invoice Follow-Up Automation',
  'Drafts follow-up communication for overdue invoices and escalates risk.',
  'paused',
  'production',
  '[{"id":"n1","type":"source","name":"Stripe Overdue Invoices"},{"id":"n2","type":"agent","name":"Lifecycle Marketing Agent"},{"id":"n3","type":"approval","name":"Compliance Review Agent"},{"id":"n4","type":"connector","name":"Gmail Follow-up"}]'::jsonb,
  '[{"id":"e1","source":"n1","target":"n2"},{"id":"e2","source":"n2","target":"n3"},{"id":"e3","source":"n3","target":"n4"}]'::jsonb,
  '{"trigger_type":"schedule","trigger_config":{"cron":"0 9 * * 2,4"},"version":1}'::jsonb,
  NULL,
  now() - interval '35 days',
  now()
),
(
  '50000000-0000-4000-8000-000000000006',
  '00000000-0000-0000-0000-000000000001',
  'Campaign Performance Summary',
  'Summarizes campaign performance and sends executive digest.',
  'active',
  'production',
  '[{"id":"n1","type":"source","name":"HubSpot Campaign Data"},{"id":"n2","type":"agent","name":"Lifecycle Marketing Agent"},{"id":"n3","type":"agent","name":"Reporting Analyst Agent"},{"id":"n4","type":"connector","name":"Notion Summary"}]'::jsonb,
  '[{"id":"e1","source":"n1","target":"n2"},{"id":"e2","source":"n2","target":"n3"},{"id":"e3","source":"n3","target":"n4"}]'::jsonb,
  '{"trigger_type":"schedule","trigger_config":{"cron":"0 10 * * 5"},"version":2}'::jsonb,
  NULL,
  now() - interval '34 days',
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
-- 6) Runs (Operator page coverage: running, pending, needs approval)
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
('60000000-0000-4000-8000-000000000001','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000001','Lead Qualification & Routing','completed','webhook','not_required',now() - interval '2 hours',now() - interval '1 hour 58 minutes',120000,NULL,'{"leadsProcessed":126,"highIntentRouted":34}'::jsonb,now() - interval '2 hours',now()),
('60000000-0000-4000-8000-000000000002','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000002','Customer Escalation Triage','running','event','not_required',now() - interval '12 minutes',NULL,NULL,NULL,'{"ticketsProcessed":8,"currentlyReviewing":"VIP-4821"}'::jsonb,now() - interval '12 minutes',now()),
('60000000-0000-4000-8000-000000000003','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000003','Weekly Executive Revenue Report','pending','schedule','pending',NULL,NULL,NULL,NULL,'{"queuePosition":1,"scheduledFor":"08:00 PT"}'::jsonb,now() - interval '20 minutes',now()),
('60000000-0000-4000-8000-000000000004','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000004','Churn Risk Detection','failed','schedule','not_required',now() - interval '5 hours',now() - interval '4 hours 55 minutes',300000,'Zendesk connector timeout during enrichment','{"accountsEvaluated":42,"failedConnector":"zendesk"}'::jsonb,now() - interval '5 hours',now()),
('60000000-0000-4000-8000-000000000005','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000005','Invoice Follow-Up Automation','completed','schedule','approved',now() - interval '1 day 1 hour',now() - interval '1 day 50 minutes',600000,NULL,'{"overdueInvoices":14,"emailsDrafted":14}'::jsonb,now() - interval '1 day 1 hour',now()),
('60000000-0000-4000-8000-000000000006','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000006','Campaign Performance Summary','completed','schedule','not_required',now() - interval '2 days',now() - interval '1 day 23 hours 50 minutes',600000,NULL,'{"campaignsReviewed":9,"topCampaign":"Q2 Retention Push"}'::jsonb,now() - interval '2 days',now()),
('60000000-0000-4000-8000-000000000007','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000001','Lead Qualification & Routing','pending','webhook','not_required',NULL,NULL,NULL,NULL,'{"queuePosition":3,"batch":"inbound-2026-04-26-17"}'::jsonb,now() - interval '6 minutes',now()),
('60000000-0000-4000-8000-000000000008','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000002','Customer Escalation Triage','completed','event','rejected',now() - interval '3 hours',now() - interval '2 hours 46 minutes',840000,NULL,'{"vipEscalations":2,"rejectedBy":"Compliance Review Agent"}'::jsonb,now() - interval '3 hours',now())
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

-- ------------------------------------------------------------
-- 7) Run Steps
-- ------------------------------------------------------------
INSERT INTO public.run_steps (
  id, org_id, run_id, name, status, order_index, started_at, completed_at, duration_ms, logs, metadata, created_at, updated_at
)
VALUES
('61000000-0000-4000-8000-000000000001','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000001','Trigger received','completed',1,now() - interval '2 hours',now() - interval '1 hour 59 minutes',60000,ARRAY['Webhook accepted'],'{"source":"hubspot"}'::jsonb,now() - interval '2 hours',now()),
('61000000-0000-4000-8000-000000000002','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000001','Data fetched','completed',2,now() - interval '1 hour 59 minutes',now() - interval '1 hour 58 minutes',70000,ARRAY['Fetched lead records'],'{"records":126}'::jsonb,now() - interval '1 hour 59 minutes',now()),
('61000000-0000-4000-8000-000000000003','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000001','Agent decision made','completed',3,now() - interval '1 hour 58 minutes',now() - interval '1 hour 58 minutes',45000,ARRAY['Scoring completed'],'{"agent":"Revenue Ops Agent"}'::jsonb,now() - interval '1 hour 58 minutes',now()),
('61000000-0000-4000-8000-000000000004','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000002','Trigger received','completed',1,now() - interval '12 minutes',now() - interval '11 minutes',60000,ARRAY['Escalation event ingested'],'{"source":"zendesk"}'::jsonb,now() - interval '12 minutes',now()),
('61000000-0000-4000-8000-000000000005','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000002','Agent decision made','running',2,now() - interval '11 minutes',NULL,NULL,ARRAY['Drafting response'],'{"agent":"Customer Support Agent"}'::jsonb,now() - interval '11 minutes',now()),
('61000000-0000-4000-8000-000000000006','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000003','Report generated','pending',1,NULL,NULL,NULL,ARRAY['Waiting for approval'],'{"report":"Weekly Executive Revenue Report"}'::jsonb,now() - interval '20 minutes',now()),
('61000000-0000-4000-8000-000000000007','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000004','Connector sync failed/retried','failed',3,now() - interval '4 hours 58 minutes',now() - interval '4 hours 55 minutes',180000,ARRAY['Zendesk timeout','Retry exhausted'],'{"connector":"zendesk","attempts":3}'::jsonb,now() - interval '4 hours 58 minutes',now()),
('61000000-0000-4000-8000-000000000008','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000005','Approval requested','completed',2,now() - interval '1 day 58 minutes',now() - interval '1 day 55 minutes',180000,ARRAY['Compliance review requested'],'{"approver":"Compliance Review Agent"}'::jsonb,now() - interval '1 day 58 minutes',now()),
('61000000-0000-4000-8000-000000000009','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000006','Slack notification drafted','completed',3,now() - interval '1 day 23 hours 56 minutes',now() - interval '1 day 23 hours 52 minutes',240000,ARRAY['Digest drafted for #exec-reports'],'{"channel":"#exec-reports"}'::jsonb,now() - interval '1 day 23 hours 56 minutes',now())
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  run_id = EXCLUDED.run_id,
  name = EXCLUDED.name,
  status = EXCLUDED.status,
  order_index = EXCLUDED.order_index,
  started_at = EXCLUDED.started_at,
  completed_at = EXCLUDED.completed_at,
  duration_ms = EXCLUDED.duration_ms,
  logs = EXCLUDED.logs,
  metadata = EXCLUDED.metadata,
  updated_at = now();

-- ------------------------------------------------------------
-- 8) Approvals
-- ------------------------------------------------------------
INSERT INTO public.approvals (
  id, org_id, run_id, title, description, type, priority, status, requested_by, reviewed_by, requested_at, reviewed_at, context, created_at, updated_at
)
VALUES
('70000000-0000-4000-8000-000000000001','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000003','Approve campaign launch','Final review before launch to enterprise segment.','workflow','high','pending','Lifecycle Marketing Agent',NULL,now() - interval '25 minutes',NULL,'{"campaign":"Enterprise Expansion Q2"}'::jsonb,now() - interval '25 minutes',now()),
('70000000-0000-4000-8000-000000000002','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000002','Approve customer escalation message','VIP customer escalation draft requires compliance sign-off.','workflow','high','pending','Customer Support Agent',NULL,now() - interval '15 minutes',NULL,'{"customerTier":"enterprise","risk":"medium"}'::jsonb,now() - interval '15 minutes',now()),
('70000000-0000-4000-8000-000000000003','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000004','Approve workflow optimization','Apply retry policy for failing Zendesk connector node.','workflow','medium','approved','Data Quality Agent','Jordan Ortiz',now() - interval '5 hours',now() - interval '4 hours 40 minutes','{"recommendation":"retry_with_backoff"}'::jsonb,now() - interval '5 hours',now()),
('70000000-0000-4000-8000-000000000004','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000006','Approve report delivery','Send weekly executive report to leadership mailing list.','workflow','medium','approved','Reporting Analyst Agent','Jordan Ortiz',now() - interval '2 days',now() - interval '1 day 23 hours 45 minutes','{"distribution":"leadership@acmecorp.com"}'::jsonb,now() - interval '2 days',now())
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
-- 9) Goals
-- ------------------------------------------------------------
INSERT INTO public.goals (
  id, org_id, objective, category, priority, frequency, department, success_metrics, connected_systems, status, created_at, updated_at
)
VALUES
('80000000-0000-4000-8000-000000000001','00000000-0000-0000-0000-000000000001','Improve MQL to SQL conversion by 15%','revenue','high','weekly','Revenue Operations','{"target":15,"currentProgress":8,"metric":"mql_to_sql_conversion"}'::jsonb,ARRAY['hubspot','salesforce','slack'],'active',now() - interval '30 days',now()),
('80000000-0000-4000-8000-000000000002','00000000-0000-0000-0000-000000000001','Reduce customer escalation response time by 30%','support','high','daily','Customer Success','{"target":30,"currentProgress":18,"metric":"escalation_response_time"}'::jsonb,ARRAY['zendesk','gmail','slack'],'active',now() - interval '28 days',now()),
('80000000-0000-4000-8000-000000000003','00000000-0000-0000-0000-000000000001','Automate weekly executive reporting','analytics','medium','weekly','Finance','{"target":"fully_automated","currentProgress":"in_review"}'::jsonb,ARRAY['stripe','salesforce','google_drive','notion'],'active',now() - interval '26 days',now()),
('80000000-0000-4000-8000-000000000004','00000000-0000-0000-0000-000000000001','Reduce failed connector syncs by 20%','platform','high','weekly','Engineering','{"target":20,"currentProgress":11,"metric":"connector_failure_rate"}'::jsonb,ARRAY['zendesk','hubspot','salesforce'],'active',now() - interval '25 days',now())
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

-- ------------------------------------------------------------
-- 10) Goal Plans
-- ------------------------------------------------------------
INSERT INTO public.goal_plans (
  id, org_id, goal_id, proposed_steps, required_connectors, required_agents, approval_gates, estimated_impact, created_at, updated_at
)
VALUES
('81000000-0000-4000-8000-000000000001','00000000-0000-0000-0000-000000000001','80000000-0000-4000-8000-000000000001','[{"step":"retrain lead scoring","owner":"Revenue Ops Agent"},{"step":"tighten routing rules","owner":"Revenue Ops Agent"}]'::jsonb,ARRAY['hubspot','salesforce'],ARRAY['30000000-0000-4000-8000-000000000001'::uuid], '[{"gate":"routing-rule-change","approverRole":"owner"}]'::jsonb,'{"expectedLift":"15%","confidence":0.77}'::jsonb,now() - interval '24 days',now()),
('81000000-0000-4000-8000-000000000002','00000000-0000-0000-0000-000000000001','80000000-0000-4000-8000-000000000002','[{"step":"auto-triage vip tickets","owner":"Customer Support Agent"},{"step":"add compliance checkpoint","owner":"Compliance Review Agent"}]'::jsonb,ARRAY['zendesk','gmail'],ARRAY['30000000-0000-4000-8000-000000000002'::uuid,'30000000-0000-4000-8000-000000000006'::uuid], '[{"gate":"vip-message-send","approverRole":"admin"}]'::jsonb,'{"expectedLift":"30% faster response","confidence":0.73}'::jsonb,now() - interval '23 days',now()),
('81000000-0000-4000-8000-000000000003','00000000-0000-0000-0000-000000000001','80000000-0000-4000-8000-000000000003','[{"step":"unify revenue feeds","owner":"Reporting Analyst Agent"},{"step":"schedule executive digest","owner":"Reporting Analyst Agent"}]'::jsonb,ARRAY['stripe','salesforce','google_drive'],ARRAY['30000000-0000-4000-8000-000000000005'::uuid], '[{"gate":"executive-distribution","approverRole":"owner"}]'::jsonb,'{"expectedLift":"4 hrs/week saved","confidence":0.86}'::jsonb,now() - interval '22 days',now()),
('81000000-0000-4000-8000-000000000004','00000000-0000-0000-0000-000000000001','80000000-0000-4000-8000-000000000004','[{"step":"introduce retry with backoff","owner":"Data Quality Agent"},{"step":"escalate after 3 failures","owner":"Compliance Review Agent"}]'::jsonb,ARRAY['zendesk','hubspot','salesforce'],ARRAY['30000000-0000-4000-8000-000000000004'::uuid,'30000000-0000-4000-8000-000000000006'::uuid], '[{"gate":"connector-policy-update","approverRole":"admin"}]'::jsonb,'{"expectedLift":"20% fewer failures","confidence":0.71}'::jsonb,now() - interval '21 days',now())
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
-- 11) Workflow Health Snapshots (7-day trend)
-- ------------------------------------------------------------
INSERT INTO public.workflow_health_snapshots (
  id, org_id, workflow_id, score, dimensions, recorded_at
)
VALUES
('82000000-0000-4000-8000-000000000001','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000001',74,'{"reliability":78,"speed":72,"cost_efficiency":70,"override_rate":22,"goal_completion":69,"decision_accuracy":76}'::jsonb,now() - interval '6 days'),
('82000000-0000-4000-8000-000000000002','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000001',76,'{"reliability":79,"speed":73,"cost_efficiency":71,"override_rate":20,"goal_completion":71,"decision_accuracy":77}'::jsonb,now() - interval '5 days'),
('82000000-0000-4000-8000-000000000003','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000001',79,'{"reliability":82,"speed":75,"cost_efficiency":73,"override_rate":19,"goal_completion":74,"decision_accuracy":80}'::jsonb,now() - interval '4 days'),
('82000000-0000-4000-8000-000000000004','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000001',81,'{"reliability":84,"speed":76,"cost_efficiency":75,"override_rate":18,"goal_completion":76,"decision_accuracy":82}'::jsonb,now() - interval '3 days'),
('82000000-0000-4000-8000-000000000005','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000001',83,'{"reliability":86,"speed":78,"cost_efficiency":76,"override_rate":16,"goal_completion":79,"decision_accuracy":84}'::jsonb,now() - interval '2 days'),
('82000000-0000-4000-8000-000000000006','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000001',85,'{"reliability":88,"speed":80,"cost_efficiency":78,"override_rate":14,"goal_completion":81,"decision_accuracy":86}'::jsonb,now() - interval '1 day'),
('82000000-0000-4000-8000-000000000007','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000001',86,'{"reliability":89,"speed":81,"cost_efficiency":79,"override_rate":13,"goal_completion":83,"decision_accuracy":87}'::jsonb,now()),
('82000000-0000-4000-8000-000000000008','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000002',69,'{"reliability":71,"speed":68,"cost_efficiency":66,"override_rate":33,"goal_completion":63,"decision_accuracy":70}'::jsonb,now() - interval '6 days'),
('82000000-0000-4000-8000-000000000009','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000002',70,'{"reliability":72,"speed":69,"cost_efficiency":67,"override_rate":31,"goal_completion":64,"decision_accuracy":71}'::jsonb,now() - interval '5 days'),
('82000000-0000-4000-8000-000000000010','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000002',72,'{"reliability":74,"speed":70,"cost_efficiency":69,"override_rate":29,"goal_completion":66,"decision_accuracy":73}'::jsonb,now() - interval '4 days'),
('82000000-0000-4000-8000-000000000011','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000002',74,'{"reliability":76,"speed":72,"cost_efficiency":70,"override_rate":26,"goal_completion":68,"decision_accuracy":75}'::jsonb,now() - interval '3 days'),
('82000000-0000-4000-8000-000000000012','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000002',75,'{"reliability":77,"speed":72,"cost_efficiency":71,"override_rate":24,"goal_completion":70,"decision_accuracy":76}'::jsonb,now() - interval '2 days'),
('82000000-0000-4000-8000-000000000013','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000002',77,'{"reliability":79,"speed":74,"cost_efficiency":72,"override_rate":22,"goal_completion":72,"decision_accuracy":78}'::jsonb,now() - interval '1 day'),
('82000000-0000-4000-8000-000000000014','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000002',78,'{"reliability":80,"speed":75,"cost_efficiency":73,"override_rate":21,"goal_completion":73,"decision_accuracy":79}'::jsonb,now()),
('82000000-0000-4000-8000-000000000015','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000003',81,'{"reliability":84,"speed":79,"cost_efficiency":80,"override_rate":17,"goal_completion":78,"decision_accuracy":83}'::jsonb,now() - interval '6 days'),
('82000000-0000-4000-8000-000000000016','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000003',82,'{"reliability":85,"speed":80,"cost_efficiency":81,"override_rate":16,"goal_completion":79,"decision_accuracy":84}'::jsonb,now() - interval '5 days'),
('82000000-0000-4000-8000-000000000017','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000003',83,'{"reliability":86,"speed":81,"cost_efficiency":82,"override_rate":15,"goal_completion":80,"decision_accuracy":85}'::jsonb,now() - interval '4 days'),
('82000000-0000-4000-8000-000000000018','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000003',84,'{"reliability":87,"speed":81,"cost_efficiency":83,"override_rate":14,"goal_completion":82,"decision_accuracy":86}'::jsonb,now() - interval '3 days'),
('82000000-0000-4000-8000-000000000019','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000003',85,'{"reliability":88,"speed":82,"cost_efficiency":84,"override_rate":13,"goal_completion":83,"decision_accuracy":87}'::jsonb,now() - interval '2 days'),
('82000000-0000-4000-8000-000000000020','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000003',86,'{"reliability":89,"speed":83,"cost_efficiency":85,"override_rate":12,"goal_completion":84,"decision_accuracy":88}'::jsonb,now() - interval '1 day'),
('82000000-0000-4000-8000-000000000021','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000003',87,'{"reliability":90,"speed":84,"cost_efficiency":86,"override_rate":11,"goal_completion":85,"decision_accuracy":89}'::jsonb,now())
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  workflow_id = EXCLUDED.workflow_id,
  score = EXCLUDED.score,
  dimensions = EXCLUDED.dimensions,
  recorded_at = EXCLUDED.recorded_at;

-- ------------------------------------------------------------
-- 12) Optimization Recommendations
-- ------------------------------------------------------------
INSERT INTO public.optimization_recommendations (
  id, org_id, workflow_id, issue, evidence, suggested_change, estimated_impact, confidence, risk_level, status, affected_nodes, created_at, updated_at
)
VALUES
('83000000-0000-4000-8000-000000000001','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000001','Reduce duplicate CRM lookups','Repeated CRM pulls add ~18% run latency.','{"action":"cache_lookup","ttlSeconds":300}'::jsonb,'{"latencyReduction":"18%","costReduction":"9%"}'::jsonb,0.84,'low','open',ARRAY['n1','n2'],now() - interval '2 days',now()),
('83000000-0000-4000-8000-000000000002','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000002','Add approval gate for high-risk customer emails','VIP draft responses exceed risk threshold in 12% of escalations.','{"action":"insert_approval_gate","riskThreshold":"high"}'::jsonb,'{"complianceRiskReduction":"22%"}'::jsonb,0.81,'medium','open',ARRAY['n3','n4'],now() - interval '1 day 12 hours',now()),
('83000000-0000-4000-8000-000000000003','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000004','Retry failed Zendesk sync before escalation','3 consecutive failures were escalated without retry.','{"action":"retry_with_backoff","maxAttempts":3}'::jsonb,'{"failureReduction":"20%","manualEscalationsReduction":"11%"}'::jsonb,0.79,'medium','open',ARRAY['n3','n5'],now() - interval '18 hours',now()),
('83000000-0000-4000-8000-000000000004','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000003','Split reporting workflow into async steps','Single synchronous run breaches SLA when data source lag exceeds 2 minutes.','{"action":"split_async","stages":["extract","compute","deliver"]}'::jsonb,'{"reliabilityGain":"14%","timeoutReduction":"35%"}'::jsonb,0.76,'low','applied',ARRAY['n1','n2','n3'],now() - interval '3 days',now()),
('83000000-0000-4000-8000-000000000005','00000000-0000-0000-0000-000000000001','50000000-0000-4000-8000-000000000001','Improve lead scoring threshold','Current threshold over-qualifies low-intent leads by ~9%.','{"action":"adjust_threshold","from":0.62,"to":0.71}'::jsonb,'{"sqlConversionLift":"6-9%"}'::jsonb,0.73,'low','open',ARRAY['n2','n3'],now() - interval '20 hours',now())
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  workflow_id = EXCLUDED.workflow_id,
  issue = EXCLUDED.issue,
  evidence = EXCLUDED.evidence,
  suggested_change = EXCLUDED.suggested_change,
  estimated_impact = EXCLUDED.estimated_impact,
  confidence = EXCLUDED.confidence,
  risk_level = EXCLUDED.risk_level,
  status = EXCLUDED.status,
  affected_nodes = EXCLUDED.affected_nodes,
  updated_at = now();

-- ------------------------------------------------------------
-- 13) Workflow A/B Tests
-- ------------------------------------------------------------
INSERT INTO public.workflow_ab_tests (
  id, org_id, workflow_id, version_a, version_b, traffic_split, metrics, status, created_at, updated_at
)
VALUES
(
  '84000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  '50000000-0000-4000-8000-000000000001',
  2,
  3,
  '{"versionA":50,"versionB":50}'::jsonb,
  '{"primary":"sql_conversion","results":{"versionA":0.21,"versionB":0.24},"sampleSize":432}'::jsonb,
  'running',
  now() - interval '6 days',
  now()
)
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  workflow_id = EXCLUDED.workflow_id,
  version_a = EXCLUDED.version_a,
  version_b = EXCLUDED.version_b,
  traffic_split = EXCLUDED.traffic_split,
  metrics = EXCLUDED.metrics,
  status = EXCLUDED.status,
  updated_at = now();

-- ------------------------------------------------------------
-- 14) Agent Council
-- ------------------------------------------------------------
INSERT INTO public.council_sessions (
  id, org_id, workflow_run_id, objective, participating_agents, debate_mode, status, final_decision, dissenting_opinions, created_at, updated_at
)
VALUES
('85000000-0000-4000-8000-000000000001','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000002','Debate whether to auto-send a high-value customer escalation response','[{"id":"30000000-0000-4000-8000-000000000002","name":"Customer Support Agent"},{"id":"30000000-0000-4000-8000-000000000006","name":"Compliance Review Agent"},{"id":"30000000-0000-4000-8000-000000000001","name":"Revenue Ops Agent"}]'::jsonb,'consensus','resolved','{"recommendation":"Require human approval before send","confidence":0.89}'::jsonb,'[{"agent":"Revenue Ops Agent","reason":"Preferred faster auto-send for SLA"}]'::jsonb,now() - interval '8 hours',now()),
('85000000-0000-4000-8000-000000000002','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000006','Decide whether to pause a campaign due to low conversion','[{"id":"30000000-0000-4000-8000-000000000003","name":"Lifecycle Marketing Agent"},{"id":"30000000-0000-4000-8000-000000000005","name":"Reporting Analyst Agent"},{"id":"30000000-0000-4000-8000-000000000006","name":"Compliance Review Agent"}]'::jsonb,'majority_vote','resolved','{"recommendation":"Pause segment-specific campaign only","confidence":0.78}'::jsonb,'[]'::jsonb,now() - interval '1 day 4 hours',now()),
('85000000-0000-4000-8000-000000000003','00000000-0000-0000-0000-000000000001','60000000-0000-4000-8000-000000000004','Review workflow optimization recommendation for Zendesk retry strategy','[{"id":"30000000-0000-4000-8000-000000000004","name":"Data Quality Agent"},{"id":"30000000-0000-4000-8000-000000000006","name":"Compliance Review Agent"},{"id":"30000000-0000-4000-8000-000000000002","name":"Customer Support Agent"}]'::jsonb,'lead_decides','in_progress',NULL,'[]'::jsonb,now() - interval '2 hours',now())
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  workflow_run_id = EXCLUDED.workflow_run_id,
  objective = EXCLUDED.objective,
  participating_agents = EXCLUDED.participating_agents,
  debate_mode = EXCLUDED.debate_mode,
  status = EXCLUDED.status,
  final_decision = EXCLUDED.final_decision,
  dissenting_opinions = EXCLUDED.dissenting_opinions,
  updated_at = now();

INSERT INTO public.council_contributions (
  id, org_id, session_id, agent_id, position, confidence, reasoning, evidence_used, created_at
)
VALUES
('86000000-0000-4000-8000-000000000001','00000000-0000-0000-0000-000000000001','85000000-0000-4000-8000-000000000001','30000000-0000-4000-8000-000000000002','Do not auto-send; include account-specific context first.',0.91,'VIP account sentiment is fragile and needs tailored response.','["ticket_history","sentiment_score"]'::jsonb,now() - interval '8 hours'),
('86000000-0000-4000-8000-000000000002','00000000-0000-0000-0000-000000000001','85000000-0000-4000-8000-000000000001','30000000-0000-4000-8000-000000000006','Require human approval before customer-visible message.',0.94,'Policy requires review for high-value escalation communications.','["policy_7.3","vip_playbook"]'::jsonb,now() - interval '8 hours'),
('86000000-0000-4000-8000-000000000003','00000000-0000-0000-0000-000000000001','85000000-0000-4000-8000-000000000001','30000000-0000-4000-8000-000000000001','Auto-send could reduce SLA breach risk.',0.66,'Fast response may prevent churn, but risk controls should remain.','["sla_dashboard"]'::jsonb,now() - interval '8 hours'),
('86000000-0000-4000-8000-000000000004','00000000-0000-0000-0000-000000000001','85000000-0000-4000-8000-000000000002','30000000-0000-4000-8000-000000000003','Pause only the underperforming segment campaign.',0.79,'Overall campaign family still meets CAC targets.','["campaign_breakdown","conversion_trend"]'::jsonb,now() - interval '1 day 4 hours'),
('86000000-0000-4000-8000-000000000005','00000000-0000-0000-0000-000000000001','85000000-0000-4000-8000-000000000002','30000000-0000-4000-8000-000000000005','Support partial pause recommendation.',0.81,'Segment-level performance variance suggests narrow intervention.','["weekly_report","channel_roi"]'::jsonb,now() - interval '1 day 4 hours'),
('86000000-0000-4000-8000-000000000006','00000000-0000-0000-0000-000000000001','85000000-0000-4000-8000-000000000002','30000000-0000-4000-8000-000000000006','Do not pause all campaigns immediately.',0.72,'Compliance risk is unchanged; broad pause has low risk value.','["policy_matrix"]'::jsonb,now() - interval '1 day 4 hours'),
('86000000-0000-4000-8000-000000000007','00000000-0000-0000-0000-000000000001','85000000-0000-4000-8000-000000000003','30000000-0000-4000-8000-000000000004','Implement retry with exponential backoff.',0.88,'Connector failure profile indicates transient API issues.','["connector_logs","failure_histogram"]'::jsonb,now() - interval '2 hours'),
('86000000-0000-4000-8000-000000000008','00000000-0000-0000-0000-000000000001','85000000-0000-4000-8000-000000000003','30000000-0000-4000-8000-000000000006','Add approval on third retry failure.',0.83,'Escalation policy requires auditable intervention points.','["compliance_policy","audit_requirements"]'::jsonb,now() - interval '2 hours'),
('86000000-0000-4000-8000-000000000009','00000000-0000-0000-0000-000000000001','85000000-0000-4000-8000-000000000003','30000000-0000-4000-8000-000000000002','Route failed retries to support queue after escalation.',0.75,'Support can triage impacted customers faster than ops fallback.','["support_capacity","customer_sla"]'::jsonb,now() - interval '2 hours')
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  session_id = EXCLUDED.session_id,
  agent_id = EXCLUDED.agent_id,
  position = EXCLUDED.position,
  confidence = EXCLUDED.confidence,
  reasoning = EXCLUDED.reasoning,
  evidence_used = EXCLUDED.evidence_used,
  created_at = EXCLUDED.created_at;

-- ------------------------------------------------------------
-- 15) Model Settings (fix duplicate id issue)
-- ------------------------------------------------------------
-- Keep existing demo-org row fresh if it already exists under a different id.
UPDATE public.model_settings
SET
  workspace_model = 'gpt-4.1',
  operator_model = 'claude-3.5-sonnet',
  agent_default_model = 'balanced',
  fallback_model = 'fast',
  allow_overrides = true,
  show_model_in_logs = true,
  updated_at = now()
WHERE org_id = '00000000-0000-0000-0000-000000000001';

-- Insert canonical id only when missing for the demo org.
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
  '99999999-9999-4999-8999-999999999991',
  '00000000-0000-0000-0000-000000000001',
  'gpt-4.1',
  'claude-3.5-sonnet',
  'balanced',
  'fast',
  true,
  true,
  now() - interval '40 days',
  now()
WHERE NOT EXISTS (
  SELECT 1
  FROM public.model_settings
  WHERE org_id = '00000000-0000-0000-0000-000000000001'
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

-- ------------------------------------------------------------
-- 16) API Keys / Webhooks
-- ------------------------------------------------------------
INSERT INTO public.api_keys (
  id,
  org_id,
  name,
  key_prefix,
  key_hash,
  status,
  last_used_at,
  created_by,
  created_at,
  updated_at
)
VALUES
(
  '87000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'Production Integrations Key',
  'grvtr_live',
  'sha256:acme-demo-key-hash-v1',
  'active',
  now() - interval '2 hours',
  NULL,
  now() - interval '30 days',
  now()
)
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  name = EXCLUDED.name,
  key_prefix = EXCLUDED.key_prefix,
  key_hash = EXCLUDED.key_hash,
  status = EXCLUDED.status,
  last_used_at = EXCLUDED.last_used_at,
  updated_at = now();

INSERT INTO public.webhooks (
  id,
  org_id,
  url,
  events,
  status,
  secret_hash,
  last_delivery_at,
  created_at,
  updated_at
)
VALUES
(
  '88000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'https://acmecorp.example/webhooks/gravitre',
  ARRAY['run.completed','approval.pending','connector.error'],
  'active',
  'sha256:acme-webhook-secret-hash',
  now() - interval '14 minutes',
  now() - interval '30 days',
  now()
)
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  url = EXCLUDED.url,
  events = EXCLUDED.events,
  status = EXCLUDED.status,
  secret_hash = EXCLUDED.secret_hash,
  last_delivery_at = EXCLUDED.last_delivery_at,
  updated_at = now();

-- ------------------------------------------------------------
-- 17) Audit Logs (insight-like timeline support)
-- ------------------------------------------------------------
INSERT INTO public.audit_logs (
  id, org_id, action, actor_id, actor, resource_type, resource_id, details, severity, created_at
)
VALUES
('89000000-0000-4000-8000-000000000001','00000000-0000-0000-0000-000000000001','weekly_revenue_report_generated',NULL,'Reporting Analyst Agent','workflow','50000000-0000-4000-8000-000000000003','{"title":"Weekly Revenue Report","summary":"Executive digest prepared"}'::jsonb,'info',now() - interval '1 day'),
('89000000-0000-4000-8000-000000000002','00000000-0000-0000-0000-000000000001','churn_risk_alert_raised',NULL,'Data Quality Agent','workflow','50000000-0000-4000-8000-000000000004','{"title":"Churn Risk Insight","accountsFlagged":4}'::jsonb,'warning',now() - interval '6 hours'),
('89000000-0000-4000-8000-000000000003','00000000-0000-0000-0000-000000000001','campaign_performance_summary_published',NULL,'Lifecycle Marketing Agent','workflow','50000000-0000-4000-8000-000000000006','{"title":"Campaign Performance Insight","topCampaign":"Retention Push"}'::jsonb,'info',now() - interval '2 hours'),
('89000000-0000-4000-8000-000000000004','00000000-0000-0000-0000-000000000001','connector_reliability_issue_detected',NULL,'Data Quality Agent','system','40000000-0000-4000-8000-000000000005','{"title":"Connector Reliability Insight","connector":"Zendesk","status":"error"}'::jsonb,'error',now() - interval '90 minutes')
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  action = EXCLUDED.action,
  actor = EXCLUDED.actor,
  resource_type = EXCLUDED.resource_type,
  resource_id = EXCLUDED.resource_id,
  details = EXCLUDED.details,
  severity = EXCLUDED.severity,
  created_at = EXCLUDED.created_at;

-- NOTE:
-- Dedicated report/insight/notification/team settings tables are not part of the
-- current contract schema in this repository. Their demo equivalents are represented
-- via workflow/report runs, goals, recommendations, model settings, org settings,
-- and audit logs.

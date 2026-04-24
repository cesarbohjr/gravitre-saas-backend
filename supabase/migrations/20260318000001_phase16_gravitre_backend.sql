-- Phase 16: Gravitre backend schema alignment (spec tables + columns)

-- Extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- Organizations: add slug + settings if missing
ALTER TABLE public.organizations
  ADD COLUMN IF NOT EXISTS slug text,
  ADD COLUMN IF NOT EXISTS settings jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS idx_organizations_slug ON public.organizations(slug);

-- Environments: add is_active if missing
ALTER TABLE public.environments
  ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;

-- Agents + versions
CREATE TABLE IF NOT EXISTS public.agents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text,
  status text NOT NULL DEFAULT 'inactive',
  role text,
  capabilities jsonb NOT NULL DEFAULT '[]'::jsonb,
  config jsonb NOT NULL DEFAULT '{}'::jsonb,
  active_version_id uuid,
  environment_id uuid REFERENCES public.environments(id) ON DELETE SET NULL,
  total_runs int NOT NULL DEFAULT 0,
  success_rate numeric(5,2) NOT NULL DEFAULT 0,
  avg_duration text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.agent_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id uuid REFERENCES public.agents(id) ON DELETE CASCADE,
  version_number text NOT NULL,
  name text,
  config jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  is_active boolean NOT NULL DEFAULT false
);

ALTER TABLE public.agents
  ADD CONSTRAINT IF NOT EXISTS fk_agents_active_version
  FOREIGN KEY (active_version_id) REFERENCES public.agent_versions(id) ON DELETE SET NULL;

-- Workflows (spec table)
CREATE TABLE IF NOT EXISTS public.workflows (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  goal text,
  description text,
  status text NOT NULL DEFAULT 'draft',
  stage text NOT NULL DEFAULT 'build',
  environment_id uuid REFERENCES public.environments(id) ON DELETE SET NULL,
  version text NOT NULL DEFAULT 'v1.0.0',
  run_count int NOT NULL DEFAULT 0,
  success_rate numeric(5,2) NOT NULL DEFAULT 0,
  last_run_at timestamptz,
  next_run_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Workflow defs (existing) alignment columns
ALTER TABLE public.workflow_defs
  ADD COLUMN IF NOT EXISTS goal text,
  ADD COLUMN IF NOT EXISTS stage text NOT NULL DEFAULT 'build',
  ADD COLUMN IF NOT EXISTS next_run_at timestamptz;

-- Workflow nodes alignment columns
ALTER TABLE public.workflow_nodes
  ADD COLUMN IF NOT EXISTS name text,
  ADD COLUMN IF NOT EXISTS description text,
  ADD COLUMN IF NOT EXISTS config jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS position_x int NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS position_y int NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS order_index int NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS system_icon text,
  ADD COLUMN IF NOT EXISTS system_name text,
  ADD COLUMN IF NOT EXISTS has_approval_gate boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS inputs jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS outputs jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS guardrails jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'needs_config';

-- Workflow connections (spec table)
CREATE TABLE IF NOT EXISTS public.workflow_connections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  workflow_id uuid REFERENCES public.workflow_defs(id) ON DELETE CASCADE,
  environment text NOT NULL DEFAULT 'production',
  from_node_id uuid REFERENCES public.workflow_nodes(id) ON DELETE CASCADE,
  to_node_id uuid REFERENCES public.workflow_nodes(id) ON DELETE CASCADE,
  edge_type text,
  condition jsonb,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workflow_id, from_node_id, to_node_id)
);

-- Workflow schedules alignment columns
ALTER TABLE public.workflow_schedules
  ADD COLUMN IF NOT EXISTS is_enabled boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS last_run_at timestamptz;

-- Runs alignment columns
ALTER TABLE public.workflow_runs
  ADD COLUMN IF NOT EXISTS approval_status text NOT NULL DEFAULT 'not_required',
  ADD COLUMN IF NOT EXISTS environment_id uuid REFERENCES public.environments(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS started_at timestamptz,
  ADD COLUMN IF NOT EXISTS duration_ms int;

-- Run steps alignment columns
ALTER TABLE public.workflow_steps
  ADD COLUMN IF NOT EXISTS node_id uuid REFERENCES public.workflow_nodes(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS name text,
  ADD COLUMN IF NOT EXISTS logs text,
  ADD COLUMN IF NOT EXISTS order_index int NOT NULL DEFAULT 0;

-- Connectors alignment columns
ALTER TABLE public.connectors
  ADD COLUMN IF NOT EXISTS name text,
  ADD COLUMN IF NOT EXISTS vendor text,
  ADD COLUMN IF NOT EXISTS description text,
  ADD COLUMN IF NOT EXISTS status text,
  ADD COLUMN IF NOT EXISTS environment_id uuid REFERENCES public.environments(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS api_key_encrypted text,
  ADD COLUMN IF NOT EXISTS webhook_url text,
  ADD COLUMN IF NOT EXISTS docs_url text,
  ADD COLUMN IF NOT EXISTS sync_frequency text NOT NULL DEFAULT '1h',
  ADD COLUMN IF NOT EXISTS last_sync_at timestamptz,
  ADD COLUMN IF NOT EXISTS last_sync_id text,
  ADD COLUMN IF NOT EXISTS records_synced int NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_connectors_deleted ON public.connectors(deleted_at) WHERE deleted_at IS NULL;

-- Sources (spec table)
CREATE TABLE IF NOT EXISTS public.sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  type text NOT NULL,
  connection_string_encrypted text,
  status text NOT NULL DEFAULT 'connected',
  environment_id uuid REFERENCES public.environments(id) ON DELETE SET NULL,
  tables_count int NOT NULL DEFAULT 0,
  last_sync_at timestamptz,
  deleted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sources_deleted ON public.sources(deleted_at) WHERE deleted_at IS NULL;

-- Approvals (spec table)
CREATE TABLE IF NOT EXISTS public.approvals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  title text NOT NULL,
  description text,
  type text NOT NULL,
  priority text NOT NULL DEFAULT 'medium',
  status text NOT NULL DEFAULT 'pending',
  gate_type text,
  requested_by text,
  requested_at timestamptz NOT NULL DEFAULT now(),
  reviewed_by text,
  reviewed_at timestamptz,
  context jsonb NOT NULL DEFAULT '{}'::jsonb,
  environment_id uuid REFERENCES public.environments(id) ON DELETE SET NULL
);

-- Audit logs (spec table)
CREATE TABLE IF NOT EXISTS public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  timestamp timestamptz NOT NULL DEFAULT now(),
  action text NOT NULL,
  action_label text,
  actor text,
  resource text,
  resource_type text,
  environment_id uuid REFERENCES public.environments(id) ON DELETE SET NULL,
  severity text NOT NULL DEFAULT 'info',
  details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON public.audit_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON public.audit_logs(action);

-- Sessions (Activities)
CREATE TABLE IF NOT EXISTS public.sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id text,
  title text,
  status text NOT NULL DEFAULT 'active',
  context_entity_type text,
  context_entity_id uuid,
  environment_id uuid REFERENCES public.environments(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS public.session_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid REFERENCES public.sessions(id) ON DELETE CASCADE,
  type text NOT NULL,
  content jsonb NOT NULL,
  timestamp timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.task_executions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid REFERENCES public.sessions(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'running',
  progress int NOT NULL DEFAULT 0,
  current_step text,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  results jsonb NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS public.operator_prompts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  icon text,
  label text,
  prompt text,
  is_active boolean NOT NULL DEFAULT true,
  order_index int NOT NULL DEFAULT 0
);

-- RAG documents alignment columns
ALTER TABLE public.rag_documents
  ADD COLUMN IF NOT EXISTS content text,
  ADD COLUMN IF NOT EXISTS embedding vector(1536),
  ADD COLUMN IF NOT EXISTS chunk_index int NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_rag_embedding ON public.rag_documents USING ivfflat (embedding vector_cosine_ops);

-- Phase 15: Spec alignment fields and soft deletes

ALTER TABLE public.environments
  ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;

ALTER TABLE public.organizations
  ADD COLUMN IF NOT EXISTS settings jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.operators
  ADD COLUMN IF NOT EXISTS active_version_id uuid REFERENCES public.operator_versions(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS environment_id uuid REFERENCES public.environments(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS total_runs int NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS success_rate numeric(5,2) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS avg_duration text,
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

ALTER TABLE public.operator_versions
  ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT false;

ALTER TABLE public.operator_sessions
  ADD COLUMN IF NOT EXISTS context_entity_type text,
  ADD COLUMN IF NOT EXISTS context_entity_id uuid;

ALTER TABLE public.workflow_defs
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'draft',
  ADD COLUMN IF NOT EXISTS version text NOT NULL DEFAULT 'v1.0.0',
  ADD COLUMN IF NOT EXISTS run_count int NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS success_rate numeric(5,2) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_run_at timestamptz,
  ADD COLUMN IF NOT EXISTS environment_id uuid REFERENCES public.environments(id) ON DELETE SET NULL;

ALTER TABLE public.workflow_nodes
  ADD COLUMN IF NOT EXISTS name text,
  ADD COLUMN IF NOT EXISTS description text,
  ADD COLUMN IF NOT EXISTS config jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS position_x int NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS position_y int NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS order_index int NOT NULL DEFAULT 0;

ALTER TABLE public.workflow_schedules
  ADD COLUMN IF NOT EXISTS last_run_at timestamptz;

ALTER TABLE public.workflow_runs
  ADD COLUMN IF NOT EXISTS environment_id uuid REFERENCES public.environments(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS duration_ms int;

ALTER TABLE public.workflow_steps
  ADD COLUMN IF NOT EXISTS logs text,
  ADD COLUMN IF NOT EXISTS order_index int NOT NULL DEFAULT 0;

ALTER TABLE public.connectors
  ADD COLUMN IF NOT EXISTS name text,
  ADD COLUMN IF NOT EXISTS vendor text,
  ADD COLUMN IF NOT EXISTS description text,
  ADD COLUMN IF NOT EXISTS api_key_encrypted text,
  ADD COLUMN IF NOT EXISTS webhook_url text,
  ADD COLUMN IF NOT EXISTS docs_url text,
  ADD COLUMN IF NOT EXISTS sync_frequency text NOT NULL DEFAULT '1h',
  ADD COLUMN IF NOT EXISTS last_sync_at timestamptz,
  ADD COLUMN IF NOT EXISTS last_sync_id text,
  ADD COLUMN IF NOT EXISTS records_synced int NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_connectors_deleted ON public.connectors(deleted_at) WHERE deleted_at IS NULL;

ALTER TABLE public.rag_sources
  ADD COLUMN IF NOT EXISTS name text,
  ADD COLUMN IF NOT EXISTS connection_string_encrypted text,
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'connected',
  ADD COLUMN IF NOT EXISTS tables_count int NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_sync_at timestamptz,
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_rag_sources_deleted ON public.rag_sources(deleted_at) WHERE deleted_at IS NULL;

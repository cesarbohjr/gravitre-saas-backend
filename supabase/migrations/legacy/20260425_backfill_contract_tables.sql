-- Backfill legacy tables into frontend-contract tables
-- Safety rules:
-- - non-destructive only
-- - idempotent inserts (ON CONFLICT DO NOTHING)
-- - legacy tables are never dropped/renamed/deleted
-- - skipped rows are logged to audit_logs where possible

-- -----------------------------------------------------------------------------
-- Helper: log skipped legacy rows into audit_logs (if table exists and org_id known)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.log_legacy_backfill_skipped(
  p_org_id uuid,
  p_legacy_table text,
  p_legacy_id uuid,
  p_reason text
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  IF p_org_id IS NULL THEN
    RETURN;
  END IF;

  IF to_regclass('public.audit_logs') IS NULL THEN
    RETURN;
  END IF;

  INSERT INTO public.audit_logs (
    org_id,
    action,
    resource_type,
    resource_id,
    details,
    severity,
    created_at
  )
  SELECT
    p_org_id,
    'legacy_backfill_skipped',
    p_legacy_table,
    p_legacy_id,
    jsonb_build_object(
      'legacy_table', p_legacy_table,
      'legacy_id', p_legacy_id,
      'reason', p_reason
    ),
    'warning',
    now()
  WHERE NOT EXISTS (
    SELECT 1
    FROM public.audit_logs al
    WHERE al.action = 'legacy_backfill_skipped'
      AND al.resource_type = p_legacy_table
      AND al.resource_id = p_legacy_id
      AND al.details->>'reason' = p_reason
  );
END;
$$;

-- -----------------------------------------------------------------------------
-- Ensure contract target columns/checks needed by backfill mapping
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF to_regclass('public.workflows') IS NOT NULL THEN
    ALTER TABLE public.workflows
      ADD COLUMN IF NOT EXISTS trigger_type text,
      ADD COLUMN IF NOT EXISTS trigger_config jsonb NOT NULL DEFAULT '{}'::jsonb,
      ADD COLUMN IF NOT EXISTS version text NOT NULL DEFAULT 'v1.0.0';
  END IF;

  IF to_regclass('public.runs') IS NOT NULL THEN
    ALTER TABLE public.runs
      ADD COLUMN IF NOT EXISTS trigger_type text,
      ADD COLUMN IF NOT EXISTS trigger_source text,
      ADD COLUMN IF NOT EXISTS duration text,
      ADD COLUMN IF NOT EXISTS output jsonb,
      ADD COLUMN IF NOT EXISTS error text,
      ADD COLUMN IF NOT EXISTS triggered_by uuid REFERENCES auth.users(id) ON DELETE SET NULL;

    ALTER TABLE public.runs DROP CONSTRAINT IF EXISTS runs_status_check;
    ALTER TABLE public.runs
      ADD CONSTRAINT runs_status_check
      CHECK (status IN ('queued', 'pending', 'running', 'completed', 'failed', 'cancelled', 'needs_approval'));
  END IF;

  IF to_regclass('public.run_steps') IS NOT NULL THEN
    ALTER TABLE public.run_steps
      ADD COLUMN IF NOT EXISTS step_index integer,
      ADD COLUMN IF NOT EXISTS node_id uuid,
      ADD COLUMN IF NOT EXISTS type text,
      ADD COLUMN IF NOT EXISTS input jsonb,
      ADD COLUMN IF NOT EXISTS output jsonb,
      ADD COLUMN IF NOT EXISTS error text,
      ADD COLUMN IF NOT EXISTS duration text;
  END IF;

  IF to_regclass('public.connected_systems') IS NOT NULL THEN
    ALTER TABLE public.connected_systems
      ADD COLUMN IF NOT EXISTS connected_at timestamptz;

    ALTER TABLE public.connected_systems DROP CONSTRAINT IF EXISTS connected_systems_status_check;
    ALTER TABLE public.connected_systems
      ADD CONSTRAINT connected_systems_status_check
      CHECK (status IN ('connected', 'disconnected', 'error', 'pending', 'expired'));
  END IF;

  IF to_regclass('public.agents') IS NOT NULL THEN
    ALTER TABLE public.agents
      ADD COLUMN IF NOT EXISTS type text;

    ALTER TABLE public.agents DROP CONSTRAINT IF EXISTS agents_status_check;
    ALTER TABLE public.agents
      ADD CONSTRAINT agents_status_check
      CHECK (status IN ('draft', 'active', 'paused', 'inactive', 'error'));
  END IF;
END;
$$;

-- -----------------------------------------------------------------------------
-- 1) workflow_defs -> workflows
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF to_regclass('public.workflow_defs') IS NULL OR to_regclass('public.workflows') IS NULL THEN
    RAISE NOTICE 'Skipping workflow_defs -> workflows backfill (missing source or target table)';
    RETURN;
  END IF;

  -- Log rows that cannot be mapped safely.
  PERFORM public.log_legacy_backfill_skipped(wd.org_id, 'workflow_defs', wd.id, 'missing_org_id')
  FROM public.workflow_defs wd
  WHERE wd.org_id IS NULL;

  PERFORM public.log_legacy_backfill_skipped(wd.org_id, 'workflow_defs', wd.id, 'missing_name')
  FROM public.workflow_defs wd
  WHERE wd.org_id IS NOT NULL
    AND (wd.name IS NULL OR btrim(wd.name) = '');

  INSERT INTO public.workflows (
    id,
    org_id,
    name,
    description,
    status,
    trigger_type,
    trigger_config,
    nodes,
    edges,
    version,
    created_at,
    updated_at,
    created_by
  )
  SELECT
    wd.id,
    wd.org_id,
    wd.name,
    wd.description,
    CASE lower(coalesce(wd.status, ''))
      WHEN 'enabled' THEN 'active'
      WHEN 'disabled' THEN 'paused'
      WHEN 'draft' THEN 'draft'
      WHEN 'archived' THEN 'archived'
      ELSE 'draft'
    END AS mapped_status,
    coalesce(to_jsonb(wd)->>'trigger_type', wd.definition->>'trigger_type', 'manual') AS trigger_type,
    coalesce((to_jsonb(wd)->'trigger_config'), (wd.definition->'trigger_config'), '{}'::jsonb) AS trigger_config,
    coalesce(wd.definition->'nodes', '[]'::jsonb) AS nodes,
    coalesce(wd.definition->'edges', '[]'::jsonb) AS edges,
    coalesce(wd.version, 'v1.0.0') AS version,
    coalesce(wd.created_at, now()) AS created_at,
    coalesce(wd.updated_at, now()) AS updated_at,
    wd.created_by
  FROM public.workflow_defs wd
  WHERE wd.org_id IS NOT NULL
    AND wd.name IS NOT NULL
    AND btrim(wd.name) <> ''
  ON CONFLICT (id) DO NOTHING;
END;
$$;

-- -----------------------------------------------------------------------------
-- 2) workflow_runs -> runs
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF to_regclass('public.workflow_runs') IS NULL OR to_regclass('public.runs') IS NULL THEN
    RAISE NOTICE 'Skipping workflow_runs -> runs backfill (missing source or target table)';
    RETURN;
  END IF;

  -- Log invalid rows before insert.
  PERFORM public.log_legacy_backfill_skipped(wr.org_id, 'workflow_runs', wr.id, 'missing_org_id')
  FROM public.workflow_runs wr
  WHERE wr.org_id IS NULL;

  PERFORM public.log_legacy_backfill_skipped(wr.org_id, 'workflow_runs', wr.id, 'invalid_workflow_fk')
  FROM public.workflow_runs wr
  WHERE wr.org_id IS NOT NULL
    AND wr.workflow_id IS NOT NULL
    AND NOT EXISTS (
      SELECT 1
      FROM public.workflows w
      WHERE w.id = wr.workflow_id
    );

  INSERT INTO public.runs (
    id,
    org_id,
    workflow_id,
    status,
    trigger_type,
    trigger_source,
    started_at,
    completed_at,
    duration,
    output,
    error,
    created_at,
    triggered_by
  )
  SELECT
    wr.id,
    wr.org_id,
    wr.workflow_id,
    CASE lower(coalesce(wr.status, ''))
      WHEN 'pending' THEN 'queued'
      WHEN 'queued' THEN 'queued'
      WHEN 'running' THEN 'running'
      WHEN 'completed' THEN 'completed'
      WHEN 'success' THEN 'completed'
      WHEN 'failed' THEN 'failed'
      WHEN 'error' THEN 'failed'
      WHEN 'cancelled' THEN 'cancelled'
      WHEN 'canceled' THEN 'cancelled'
      WHEN 'needs_approval' THEN 'needs_approval'
      ELSE 'queued'
    END AS mapped_status,
    coalesce(wr.trigger_type, 'manual') AS trigger_type,
    coalesce(to_jsonb(wr)->>'trigger_source', to_jsonb(wr)->>'run_type', 'manual') AS trigger_source,
    coalesce(wr.started_at, wr.created_at, now()) AS started_at,
    wr.completed_at,
    coalesce(
      to_jsonb(wr)->>'duration',
      CASE WHEN wr.duration_ms IS NOT NULL THEN wr.duration_ms::text ELSE NULL END
    ) AS duration,
    coalesce(to_jsonb(wr)->'output', NULL::jsonb) AS output,
    coalesce(to_jsonb(wr)->>'error', wr.error_message) AS error,
    coalesce(wr.created_at, now()) AS created_at,
    wr.triggered_by
  FROM public.workflow_runs wr
  WHERE wr.org_id IS NOT NULL
    AND (
      wr.workflow_id IS NULL
      OR EXISTS (SELECT 1 FROM public.workflows w WHERE w.id = wr.workflow_id)
    )
  ON CONFLICT (id) DO NOTHING;
END;
$$;

-- -----------------------------------------------------------------------------
-- 3) workflow_steps -> run_steps
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF to_regclass('public.workflow_steps') IS NULL OR to_regclass('public.run_steps') IS NULL THEN
    RAISE NOTICE 'Skipping workflow_steps -> run_steps backfill (missing source or target table)';
    RETURN;
  END IF;

  PERFORM public.log_legacy_backfill_skipped(ws.org_id, 'workflow_steps', ws.id, 'missing_org_id')
  FROM public.workflow_steps ws
  WHERE ws.org_id IS NULL;

  PERFORM public.log_legacy_backfill_skipped(ws.org_id, 'workflow_steps', ws.id, 'invalid_run_fk')
  FROM public.workflow_steps ws
  WHERE ws.org_id IS NOT NULL
    AND NOT EXISTS (
      SELECT 1
      FROM public.runs r
      WHERE r.id = ws.run_id
    );

  INSERT INTO public.run_steps (
    id,
    org_id,
    run_id,
    step_index,
    node_id,
    name,
    type,
    status,
    input,
    output,
    error,
    started_at,
    completed_at,
    duration
  )
  SELECT
    ws.id,
    ws.org_id,
    ws.run_id,
    ws.step_index,
    coalesce((to_jsonb(ws)->>'node_id')::uuid, NULL) AS node_id,
    coalesce(ws.name, ws.step_name) AS name,
    coalesce(to_jsonb(ws)->>'type', ws.step_type) AS type,
    CASE lower(coalesce(ws.status, ''))
      WHEN 'pending' THEN 'pending'
      WHEN 'running' THEN 'running'
      WHEN 'completed' THEN 'completed'
      WHEN 'success' THEN 'completed'
      WHEN 'failed' THEN 'failed'
      WHEN 'error' THEN 'failed'
      WHEN 'skipped' THEN 'skipped'
      ELSE 'pending'
    END AS mapped_status,
    coalesce(to_jsonb(ws)->'input', ws.input_snapshot, NULL::jsonb) AS input,
    coalesce(to_jsonb(ws)->'output', ws.output_snapshot, NULL::jsonb) AS output,
    coalesce(to_jsonb(ws)->>'error', ws.error_message, ws.error_code) AS error,
    ws.started_at,
    ws.completed_at,
    coalesce(
      to_jsonb(ws)->>'duration',
      CASE
        WHEN ws.completed_at IS NOT NULL AND ws.started_at IS NOT NULL
          THEN extract(epoch FROM (ws.completed_at - ws.started_at))::bigint::text
        ELSE NULL
      END
    ) AS duration
  FROM public.workflow_steps ws
  WHERE ws.org_id IS NOT NULL
    AND EXISTS (
      SELECT 1
      FROM public.runs r
      WHERE r.id = ws.run_id
    )
  ON CONFLICT (id) DO NOTHING;
END;
$$;

-- -----------------------------------------------------------------------------
-- 4) connectors -> connected_systems
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF to_regclass('public.connectors') IS NULL OR to_regclass('public.connected_systems') IS NULL THEN
    RAISE NOTICE 'Skipping connectors -> connected_systems backfill (missing source or target table)';
    RETURN;
  END IF;

  PERFORM public.log_legacy_backfill_skipped(c.org_id, 'connectors', c.id, 'missing_org_id')
  FROM public.connectors c
  WHERE c.org_id IS NULL;

  INSERT INTO public.connected_systems (
    id,
    org_id,
    system_key,
    type,
    name,
    status,
    config,
    connected_at,
    last_synced_at,
    created_at,
    updated_at
  )
  SELECT
    c.id,
    c.org_id,
    coalesce(
      nullif(c.name, ''),
      nullif(c.type, ''),
      concat('system-', substr(c.id::text, 1, 8))
    ) AS system_key,
    c.type,
    coalesce(c.name, initcap(replace(c.type, '_', ' ')), 'Connected System') AS name,
    CASE lower(coalesce(c.status, ''))
      WHEN 'active' THEN 'connected'
      WHEN 'connected' THEN 'connected'
      WHEN 'error' THEN 'error'
      WHEN 'expired' THEN 'expired'
      WHEN 'pending' THEN 'pending'
      WHEN 'disabled' THEN 'error'
      ELSE 'pending'
    END AS mapped_status,
    coalesce(c.config, '{}'::jsonb) AS config,
    coalesce((to_jsonb(c)->>'connected_at')::timestamptz, c.created_at, now()) AS connected_at,
    c.last_sync_at,
    coalesce(c.created_at, now()) AS created_at,
    coalesce(c.updated_at, now()) AS updated_at
  FROM public.connectors c
  WHERE c.org_id IS NOT NULL
  ON CONFLICT (id) DO NOTHING;
END;
$$;

-- -----------------------------------------------------------------------------
-- 5) operators -> agents
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF to_regclass('public.operators') IS NULL OR to_regclass('public.agents') IS NULL THEN
    RAISE NOTICE 'Skipping operators -> agents backfill (missing source or target table)';
    RETURN;
  END IF;

  PERFORM public.log_legacy_backfill_skipped(o.org_id, 'operators', o.id, 'missing_org_id')
  FROM public.operators o
  WHERE o.org_id IS NULL;

  PERFORM public.log_legacy_backfill_skipped(o.org_id, 'operators', o.id, 'missing_name')
  FROM public.operators o
  WHERE o.org_id IS NOT NULL
    AND (o.name IS NULL OR btrim(o.name) = '');

  INSERT INTO public.agents (
    id,
    org_id,
    name,
    description,
    status,
    type,
    capabilities,
    model,
    config,
    created_at,
    updated_at,
    created_by
  )
  SELECT
    o.id,
    o.org_id,
    o.name,
    o.description,
    CASE lower(coalesce(o.status, ''))
      WHEN 'active' THEN 'active'
      WHEN 'enabled' THEN 'active'
      WHEN 'paused' THEN 'paused'
      WHEN 'disabled' THEN 'paused'
      WHEN 'error' THEN 'error'
      WHEN 'draft' THEN 'draft'
      ELSE 'draft'
    END AS mapped_status,
    CASE lower(coalesce(to_jsonb(o)->>'type', ''))
      WHEN 'operator' THEN 'operator'
      WHEN 'worker' THEN 'worker'
      WHEN 'reviewer' THEN 'reviewer'
      ELSE 'worker'
    END AS mapped_type,
    coalesce(o.capabilities, '[]'::jsonb) AS capabilities,
    coalesce(to_jsonb(o)->>'model', 'auto') AS model,
    coalesce(o.config, '{}'::jsonb) AS config,
    coalesce(o.created_at, now()) AS created_at,
    coalesce(o.updated_at, now()) AS updated_at,
    o.created_by
  FROM public.operators o
  WHERE o.org_id IS NOT NULL
    AND o.name IS NOT NULL
    AND btrim(o.name) <> ''
  ON CONFLICT (id) DO NOTHING;
END;
$$;

-- -----------------------------------------------------------------------------
-- Verification helpers (non-destructive; run manually)
-- -----------------------------------------------------------------------------
-- SELECT COUNT(*) FROM public.workflows;
-- SELECT COUNT(*) FROM public.runs;
-- SELECT COUNT(*) FROM public.run_steps;
-- SELECT COUNT(*) FROM public.connected_systems;
-- SELECT COUNT(*) FROM public.agents;

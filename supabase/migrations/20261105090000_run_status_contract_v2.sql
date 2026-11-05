-- PR #605: versioned lossless run-status contract v2.
-- Migration is staged in the draft PR, NOT executed against live Supabase.
-- Apply on verified target DB in the release sequence, before deploying v2
-- application writers. Existing rows remain unchanged by this migration.
--
-- v2 retains the original workflow lifecycle in metadata and represents
-- partial_success and flagged_for_review as distinct statuses.
-- A failed mirror is not allowed to silently commit an inconsistent run
-- projection. For high-availability operations ensure the migration and
-- contract tests are completed before enabling this trigger in production.

ALTER TABLE public.runs DROP CONSTRAINT IF EXISTS runs_status_check;
ALTER TABLE public.runs ADD CONSTRAINT runs_status_check CHECK (
  status IN (
    'queued', 'pending', 'running', 'completed', 'failed', 'cancelled',
    'needs_approval', 'paused', 'partial_success', 'flagged_for_review'
  )
);

COMMENT ON CONSTRAINT runs_status_check ON public.runs IS
  'PR605 v2: preserves partial success and review-required independently of verified completion';

CREATE OR REPLACE FUNCTION public.mirror_workflow_run_status_to_contract()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  mapped_status text;
  mapped_approval text;
BEGIN
  mapped_status := CASE lower(coalesce(NEW.status, ''))
    WHEN 'pending' THEN 'queued'
    WHEN 'queued' THEN 'queued'
    WHEN 'pending_approval' THEN 'needs_approval'
    WHEN 'awaiting_approval' THEN 'needs_approval'
    WHEN 'needs_approval' THEN 'needs_approval'
    WHEN 'success' THEN 'completed'
    WHEN 'partial_success' THEN 'partial_success'
    WHEN 'flagged_for_review' THEN 'flagged_for_review'
    WHEN 'verifying' THEN 'running'
    WHEN 'verification_inconclusive' THEN 'failed'
    WHEN 'error' THEN 'failed'
    WHEN 'canceled' THEN 'cancelled'
    WHEN 'running' THEN 'running'
    WHEN 'completed' THEN 'completed'
    WHEN 'failed' THEN 'failed'
    WHEN 'cancelled' THEN 'cancelled'
    WHEN 'paused' THEN 'paused'
    ELSE NULL
  END;
  IF mapped_status IS NULL THEN
    RAISE EXCEPTION 'unsupported workflow run status for v2 mirror';
  END IF;

  mapped_approval := CASE lower(coalesce(NEW.approval_status, ''))
    WHEN '' THEN 'not_required'
    WHEN 'pending_approval' THEN 'pending'
    ELSE lower(NEW.approval_status)
  END;

  INSERT INTO public.runs AS r (
    id, org_id, workflow_id, status, trigger, approval_status,
    started_at, completed_at, error_message, metadata, updated_at
  )
  VALUES (
    NEW.id,
    NEW.org_id,
    NEW.workflow_id,
    mapped_status,
    coalesce(NEW.trigger_type, NEW.run_type, 'manual'),
    mapped_approval,
    NEW.created_at,
    NEW.completed_at,
    NEW.error_message,
    jsonb_build_object(
      'run_type', NEW.run_type,
      'run_hash', NEW.run_hash,
      'environment', NEW.environment,
      'execution_lifecycle', NEW.status,
      'status_contract_version', 2,
      'mirrored_by', 'workflow_runs_status_trigger'
    ),
    now()
  )
  ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    approval_status = COALESCE(EXCLUDED.approval_status, r.approval_status),
    completed_at = EXCLUDED.completed_at,
    error_message = EXCLUDED.error_message,
    metadata = COALESCE(r.metadata, '{}'::jsonb) || EXCLUDED.metadata,
    updated_at = now();

  RETURN NEW;
  -- IMPORTANT: No WHEN OTHERS warning-and-continue. If the mirror fails, the
  -- workflow update must fail atomically rather than claiming an incorrect
  -- terminal result. Test all callers in ephemeral PostgreSQL first.
END;
$$;

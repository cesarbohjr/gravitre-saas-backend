-- Canonical connector-write lifecycle truth.
-- A provider accepting a mutation is not a terminal success. Runs stay
-- non-terminal while source-of-record verification is in flight and may end
-- explicitly inconclusive without ever emitting completed.
ALTER TABLE public.workflow_runs
  DROP CONSTRAINT IF EXISTS workflow_runs_status_check;

ALTER TABLE public.workflow_runs
  ADD CONSTRAINT workflow_runs_status_check
  CHECK (
    status IN (
      'running',
      'verifying',
      'completed',
      'failed',
      'cancelled',
      'pending_approval',
      'awaiting_approval',
      'paused',
      'partial_success',
      'flagged_for_review',
      'verification_inconclusive'
    )
  );

COMMENT ON CONSTRAINT workflow_runs_status_check ON public.workflow_runs IS
  'Write lifecycle: provider acceptance may transition to verifying; completed requires source-of-record proof; verification_inconclusive is terminal non-success.';


-- Contract runs keep their established coarse status vocabulary. Preserve the
-- richer write lifecycle on workflow_runs/parameters while mirroring safely:
-- verifying behaves as running; inconclusive behaves as non-success/failed.
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
    WHEN 'pending_approval' THEN 'needs_approval'
    WHEN 'awaiting_approval' THEN 'needs_approval'
    WHEN 'partial_success' THEN 'completed'
    WHEN 'verifying' THEN 'running'
    WHEN 'verification_inconclusive' THEN 'failed'
    WHEN 'error' THEN 'failed'
    ELSE lower(coalesce(NEW.status, 'running'))
  END;

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
EXCEPTION
  WHEN undefined_table THEN
    RETURN NEW;
  WHEN OTHERS THEN
    RAISE WARNING 'mirror_workflow_run_status_to_contract failed run_id=%: %', NEW.id, SQLERRM;
    RETURN NEW;
END;
$$;

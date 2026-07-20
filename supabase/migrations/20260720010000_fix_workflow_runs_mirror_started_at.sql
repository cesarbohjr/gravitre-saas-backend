-- STA-271 fix: workflow_runs has created_at, not started_at.
-- Prior trigger failed with: record "new" has no field "started_at"

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
    WHEN 'error' THEN 'failed'
    ELSE lower(coalesce(NEW.status, 'running'))
  END;

  mapped_approval := CASE lower(coalesce(NEW.approval_status, ''))
    WHEN '' THEN 'not_required'
    WHEN 'pending_approval' THEN 'pending'
    ELSE lower(NEW.approval_status)
  END;

  INSERT INTO public.runs AS r (
    id,
    org_id,
    workflow_id,
    status,
    trigger,
    approval_status,
    started_at,
    completed_at,
    error_message,
    metadata,
    updated_at
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
      'mirrored_by', 'workflow_runs_status_trigger'
    ),
    now()
  )
  ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    approval_status = COALESCE(EXCLUDED.approval_status, r.approval_status),
    completed_at = EXCLUDED.completed_at,
    error_message = EXCLUDED.error_message,
    metadata = COALESCE(r.metadata, '{}'::jsonb) || jsonb_build_object(
      'mirrored_by', 'workflow_runs_status_trigger'
    ),
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

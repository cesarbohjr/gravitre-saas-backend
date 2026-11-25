-- Additive candidate: no legacy payload identifiers are backfilled.
ALTER TABLE public.agent_jobs ADD COLUMN IF NOT EXISTS bound_run_id uuid
  REFERENCES public.workflow_runs(id);
CREATE UNIQUE INDEX IF NOT EXISTS agent_jobs_bound_run_unique
  ON public.agent_jobs(bound_run_id) WHERE bound_run_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.guard_agent_job_run_binding()
RETURNS trigger LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF OLD.bound_run_id IS NOT NULL AND
       (NEW.bound_run_id IS DISTINCT FROM OLD.bound_run_id OR
        NEW.org_id IS DISTINCT FROM OLD.org_id OR
        NEW.environment IS DISTINCT FROM OLD.environment OR
        NEW.created_by IS DISTINCT FROM OLD.created_by) THEN
      RAISE EXCEPTION 'Persisted job run binding is immutable';
    END IF;
  END IF;
  IF NEW.bound_run_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public.workflow_runs r
    WHERE r.id = NEW.bound_run_id AND r.org_id = NEW.org_id
      AND r.environment = NEW.environment AND r.triggered_by = NEW.created_by
  ) THEN
    RAISE EXCEPTION 'Invalid persisted job run identity';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS agent_job_run_binding_guard ON public.agent_jobs;
CREATE TRIGGER agent_job_run_binding_guard BEFORE INSERT OR UPDATE
  ON public.agent_jobs FOR EACH ROW EXECUTE FUNCTION public.guard_agent_job_run_binding();

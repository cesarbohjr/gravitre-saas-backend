-- Per-run cost: attribute model calls to the workflow run (and chat turn) that made them.
--
-- model_calls had no run or turn reference, so the cost of one run (for example
-- the Freshservice ticket workflow) could not be measured. Expand only: two
-- nullable columns and a partial index; existing rows and writers are unchanged.
-- The backend writes these columns only when present (it retries an insert
-- without them otherwise), so code and migration can deploy in either order.
--
-- Preflight (read-only):
--   select count(*), pg_size_pretty(pg_total_relation_size('public.model_calls')) from public.model_calls;
--   (2026-10-13: 17,011 rows, 5.6 MB)
--
-- Rollback: drop the index and the two columns (no other object depends on them).

SET lock_timeout = '5s';

ALTER TABLE public.model_calls
  ADD COLUMN IF NOT EXISTS run_id uuid,
  ADD COLUMN IF NOT EXISTS turn_id text;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
     WHERE conrelid = 'public.model_calls'::regclass AND conname = 'model_calls_run_id_fkey'
  ) THEN
    ALTER TABLE public.model_calls
      ADD CONSTRAINT model_calls_run_id_fkey FOREIGN KEY (run_id)
      REFERENCES public.workflow_runs(id) ON DELETE SET NULL NOT VALID;
  END IF;
END;
$$;

ALTER TABLE public.model_calls VALIDATE CONSTRAINT model_calls_run_id_fkey;

CREATE INDEX IF NOT EXISTS idx_model_calls_run_id
  ON public.model_calls (run_id) WHERE run_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_model_calls_org_turn
  ON public.model_calls (org_id, turn_id) WHERE turn_id IS NOT NULL;

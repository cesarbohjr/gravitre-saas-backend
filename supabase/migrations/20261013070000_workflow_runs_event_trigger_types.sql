-- Event-triggered runs from Salesforce, Segment, PagerDuty and Freshservice can be created.
--
-- The trigger services insert workflow_runs.trigger_type = 'salesforce' / 'segment' /
-- 'pagerduty', but workflow_runs_trigger_type_check (20260602110000) allows only
-- manual, schedule, rollback, webhook, api, hubspot (confirmed in production
-- 2026-10-13). Every such insert failed, and because the webhook receipt was
-- already claimed, provider retries were skipped as duplicates: the event was lost.
-- 'freshservice' is added for the Release 3 Freshservice trigger.
--
-- Added NOT VALID then validated, so the table is not held under an exclusive lock
-- while existing rows are checked.
--
-- Preflight (read-only):
--   select pg_get_constraintdef(oid) from pg_constraint
--    where conrelid = 'public.workflow_runs'::regclass and conname = 'workflow_runs_trigger_type_check';
--   select trigger_type, count(*) from public.workflow_runs group by 1;
--
-- Rollback: recreate the constraint with the previous list (only if no rows use the
-- new values).

ALTER TABLE public.workflow_runs
  DROP CONSTRAINT IF EXISTS workflow_runs_trigger_type_check;

ALTER TABLE public.workflow_runs
  ADD CONSTRAINT workflow_runs_trigger_type_check
  CHECK (trigger_type IN (
    'manual', 'schedule', 'rollback', 'webhook', 'api', 'hubspot',
    'salesforce', 'segment', 'pagerduty', 'freshservice'
  )) NOT VALID;

ALTER TABLE public.workflow_runs
  VALIDATE CONSTRAINT workflow_runs_trigger_type_check;

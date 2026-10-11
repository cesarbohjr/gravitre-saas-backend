-- Phase 2A production checks (read-only). Run in the Supabase SQL editor for project
-- smyeexlrqdpymwjmgzqu BEFORE applying 20261011220000_domain_event_outbox.sql.
-- Nothing here writes. Paste the results back into the Phase 2A PR.

-- A. Migration preflight -------------------------------------------------------
SELECT to_regclass('public.domain_event_outbox') AS outbox_table;            -- expect NULL

SELECT proname FROM pg_proc
 WHERE pronamespace = 'public'::regnamespace
   AND proname IN ('claim_domain_events','complete_domain_event','fail_domain_event',
                   'domain_event_outbox_stats','prune_domain_events',
                   'emit_workflow_run_terminal_event','emit_connector_disconnected_event');
                                                                              -- expect 0 rows
SELECT tgname FROM pg_trigger
 WHERE tgname IN ('workflow_runs_emit_terminal_event','connectors_emit_disconnected_event');
                                                                              -- expect 0 rows
SELECT table_name, column_name, data_type FROM information_schema.columns
 WHERE table_schema = 'public'
   AND ((table_name = 'workflow_runs' AND column_name IN ('id','org_id','workflow_id','status','completed_at'))
     OR (table_name = 'connectors'    AND column_name IN ('id','org_id','type','deleted_at')))
 ORDER BY 1, 2;                                                               -- expect 9 rows

SELECT version();                                                             -- expect PostgreSQL >= 13
SELECT extname FROM pg_extension WHERE extname = 'pgcrypto';                  -- informational

-- Existing triggers on the two tables (the new ones are AFTER triggers and run after these)
SELECT event_object_table, trigger_name, action_timing, event_manipulation
  FROM information_schema.triggers
 WHERE event_object_schema = 'public' AND event_object_table IN ('workflow_runs','connectors')
 ORDER BY 1, 2;

-- B. Expected event volume ---------------------------------------------------
SELECT date_trunc('day', completed_at) AS day, status, count(*)
  FROM public.workflow_runs
 WHERE completed_at > now() - interval '30 days'
 GROUP BY 1, 2 ORDER BY 1 DESC, 2;
SELECT count(*) AS connectors_soft_deleted_30d
  FROM public.connectors WHERE deleted_at > now() - interval '30 days';
SELECT pg_size_pretty(pg_total_relation_size('public.workflow_runs')) AS workflow_runs_size,
       (SELECT count(*) FROM public.workflow_runs) AS workflow_runs_rows;

-- C. Outstanding Phase 1 schema checks ---------------------------------------
-- agent_memories.agent_id nullable?
SELECT column_name, is_nullable, data_type FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'agent_memories' AND column_name = 'agent_id';
-- agent_action_outcomes columns
SELECT column_name, data_type, is_nullable FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'agent_action_outcomes'
 ORDER BY ordinal_position;

-- D. Not SQL: Railway variables to read (do not change) ----------------------
--   TEMPORAL_HOST            (set / unset; value not needed)
--   DOMAIN_EVENT_RELAY_ENABLED must be absent or false until Phase 2B consumers ship.

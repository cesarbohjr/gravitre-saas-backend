-- Phase 3 advisor burn-down: covering indexes for hottest unindexed FKs
-- (applied live 2026-08-06 via Management API; kept here for schema history).

CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_id_fk ON public.audit_logs (actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor_id_fk ON public.audit_events (actor_id);
CREATE INDEX IF NOT EXISTS idx_model_calls_trained_model_id_fk ON public.model_calls (trained_model_id);
CREATE INDEX IF NOT EXISTS idx_runs_triggered_by_fk ON public.runs (triggered_by);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow_version_id_fk ON public.workflow_runs (workflow_version_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_rollback_of_run_id_fk ON public.workflow_runs (rollback_of_run_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_environment_id_fk ON public.workflow_runs (environment_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_triggered_by_fk ON public.workflow_runs (triggered_by);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_schedule_id_fk ON public.workflow_runs (schedule_id);
CREATE INDEX IF NOT EXISTS idx_org_billing_plan_code_fk ON public.org_billing (plan_code);
CREATE INDEX IF NOT EXISTS idx_agent_tool_permissions_granted_by_fk ON public.agent_tool_permissions (granted_by);

-- Duplicate index burn-down (optimization_recommendations had two org indexes).
DROP INDEX IF EXISTS public.optimization_recommendations_org_id_idx;

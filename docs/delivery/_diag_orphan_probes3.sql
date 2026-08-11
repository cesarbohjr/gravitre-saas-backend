select
  exists (select 1 from pg_indexes where schemaname='public' and indexname='idx_audit_logs_actor_id_fk') as idx_audit_logs_actor,
  exists (select 1 from pg_indexes where schemaname='public' and indexname='idx_workflow_runs_schedule_id_fk') as idx_wr_schedule,
  exists (select 1 from pg_indexes where schemaname='public' and indexname='idx_org_billing_plan_code_fk') as idx_org_billing_plan,
  (select c.relrowsecurity from pg_class c join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname='agent_execution_interrupts') as rls_agent_execution_interrupts,
  (select c.relrowsecurity from pg_class c join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname='intelligence_outcome_events') as rls_intelligence_outcome_events,
  exists (
    select 1 from pg_proc p
    join pg_namespace n on n.oid=p.pronamespace
    where n.nspname='public' and p.proname='handle_new_user'
      and pg_get_functiondef(p.oid) ilike '%owner%'
  ) as handle_new_user_mentions_owner,
  (select count(*)::int from public.organization_members where role='owner') as owner_member_count;

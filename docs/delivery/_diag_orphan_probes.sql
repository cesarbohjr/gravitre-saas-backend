-- DIAGNOSIS: confirm objects for local-only orphan migrations before repair --status applied
select
  to_regclass('public.department_resource_assignments') is not null as dept_assignments_exists,
  exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='users' and column_name='job_title'
  ) as users_job_title,
  exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='users' and column_name='department'
  ) as users_department,
  exists (
    select 1 from pg_indexes
    where schemaname='public' and indexname='idx_audit_events_org_action_created'
  ) as audit_events_org_action_idx,
  exists (
    select 1 from information_schema.check_constraints c
    join information_schema.constraint_column_usage u
      on c.constraint_name = u.constraint_name
    where u.table_name='workflow_runs' and c.check_clause ilike '%flagged_for_review%'
  ) as workflow_runs_flagged_check,
  exists (
    select 1 from public.billing_plans
    where code='node'
      and (features ? 'research_lookups_per_month')
      and (overage_rates ? 'research_lookup')
  ) as research_keys_on_node,
  exists (
    select 1 from public.platform_admins
    where email = 'cesar@gravitre.app'
  ) as platform_admin_gravitre_app,
  exists (
    select 1 from public.environments where lower(name) = 'production'
  ) as production_env_exists;

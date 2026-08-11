-- DIAGNOSIS ONLY
select version, name, created_by
from supabase_migrations.schema_migrations
where name ilike '%org_creator%'
   or name ilike '%seed_production%'
   or name ilike '%platform_admin%'
   or name ilike '%job_title%'
   or name ilike '%enable_rls%'
   or name ilike '%audit_events_org%'
   or name ilike '%perf_advisor%'
   or name ilike '%flagged_for_review%'
   or name ilike '%research_lookup%'
   or name ilike '%restore_billing%'
order by version::text;

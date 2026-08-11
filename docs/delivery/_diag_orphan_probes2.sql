-- More orphan probes
select
  (select count(*) from pg_indexes where schemaname='public' and indexname like 'idx_%' and indexdef ilike '%REFERENCES%' ) as ignored,
  exists (select 1 from pg_indexes where schemaname='public' and indexname = 'idx_audit_events_org_id_action_created_at') as alt_audit_idx,
  exists (
    select 1 from pg_tables t
    join pg_class c on c.relname = t.tablename
    join pg_namespace n on n.oid = c.relnamespace and n.nspname='public'
    where t.schemaname='public' and c.relrowsecurity = true
      and t.tablename in (
        'intelligence_learning_signals',
        'org_entity_relationships',
        'research_monitors'
      )
  ) as sample_intel_rls_on;

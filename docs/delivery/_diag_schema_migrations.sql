-- DIAGNOSIS ONLY (read-only)
select *
from supabase_migrations.schema_migrations
where version::text >= '20260725'
order by version::text
limit 80;

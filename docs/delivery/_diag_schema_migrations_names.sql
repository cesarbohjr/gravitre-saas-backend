-- DIAGNOSIS ONLY (read-only): version + name + created_by for drift window
select version, name, created_by
from supabase_migrations.schema_migrations
where version::text >= '20260725'
order by version::text;

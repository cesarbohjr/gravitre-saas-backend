-- Add the remaining qualified-prospecting connectors without discarding existing providers.
-- Safe on databases where any/all types already exist.
do $migration$
declare v_definition text; v_sql text;
begin
 select pg_get_constraintdef(oid) into v_definition
 from pg_constraint where conrelid='public.connectors'::regclass
   and conname='connectors_type_check' and contype='c';
 if v_definition is null or position('''hubspot''::text' in v_definition)=0 then
   raise exception 'unexpected connector type constraint; inspect before migration';
 end if;
 v_sql=v_definition;
 if position('''quickmail''::text' in v_sql)=0 then
  v_sql=replace(v_sql,'''hubspot''::text','''hubspot''::text, ''quickmail''::text');
 end if;
 if position('''hunter''::text' in v_sql)=0 then
  v_sql=replace(v_sql,'''hubspot''::text','''hubspot''::text, ''hunter''::text');
 end if;
 if position('''snov''::text' in v_sql)=0 then
  v_sql=replace(v_sql,'''hubspot''::text','''hubspot''::text, ''snov''::text');
 end if;
 if position('''emailable''::text' in v_sql)=0 then
  v_sql=replace(v_sql,'''hubspot''::text','''hubspot''::text, ''emailable''::text');
 end if;
 if position('''millionverifier''::text' in v_sql)=0 then
  v_sql=replace(v_sql,'''hubspot''::text','''hubspot''::text, ''millionverifier''::text');
 end if;
 if v_sql <> v_definition then
  alter table public.connectors drop constraint connectors_type_check;
  execute format('alter table public.connectors add constraint connectors_type_check %s',v_sql);
 end if;
end
$migration$;
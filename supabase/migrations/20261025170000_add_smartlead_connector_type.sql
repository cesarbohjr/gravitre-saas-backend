-- Preserve the existing connector type allowlist while adding Smartlead.
-- Idempotent for environments where the provider is already included.
do $migration$
declare
  existing_definition text;
  updated_definition text;
begin
  select pg_get_constraintdef(c.oid) into existing_definition
  from pg_constraint c
  where c.conrelid='public.connectors'::regclass
    and c.conname='connectors_type_check' and c.contype='c';
  if existing_definition is null then
    raise exception 'connectors_type_check is missing; cannot safely modify provider allowlist';
  end if;
  if position('''smartlead''::text' in existing_definition)>0 then
    return;
  end if;
  if position('''instantly''::text' in existing_definition)=0 then
    raise exception 'unexpected connector type allowlist; manual reconciliation required';
  end if;
  updated_definition=replace(existing_definition,
    '''instantly''::text', '''instantly''::text, ''smartlead''::text');
  alter table public.connectors drop constraint connectors_type_check;
  execute format('alter table public.connectors add constraint connectors_type_check %s', updated_definition);
end
$migration$;
-- Atomic sweep admission. A per-org transaction advisory lock serializes
-- admission, including requests arriving on different API instances.
create or replace function public.admit_intelligence_overview_sweep(
  p_org_id uuid, p_requested_by uuid, p_scope jsonb,
  p_daily_limit integer default 5
) returns public.intelligence_overview_sweeps
language plpgsql security definer set search_path = public
as $$
declare
  v_row public.intelligence_overview_sweeps;
  v_count integer;
begin
  if auth.role() <> 'service_role' then
    raise exception 'service role required' using errcode = '42501';
  end if;
  if p_daily_limit < 1 or p_daily_limit > 100 then
    raise exception 'invalid sweep quota' using errcode = '22023';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(p_org_id::text, 612009));
  select * into v_row from public.intelligence_overview_sweeps
   where org_id = p_org_id and status in ('queued','running')
   order by created_at desc limit 1;
  if found then
    return v_row;
  end if;
  select count(*) into v_count from public.intelligence_overview_sweeps
    where org_id = p_org_id and created_at >= now() - interval '24 hours';
  if v_count >= p_daily_limit then
    raise exception 'daily sweep quota exceeded' using errcode = 'P0001';
  end if;
  insert into public.intelligence_overview_sweeps
    (org_id, requested_by, scope, status)
    values (p_org_id, p_requested_by, coalesce(p_scope, '{}'::jsonb), 'queued')
    returning * into v_row;
  return v_row;
end;
$$;
revoke all on function public.admit_intelligence_overview_sweep(uuid,uuid,jsonb,integer) from public, anon, authenticated;
grant execute on function public.admit_intelligence_overview_sweep(uuid,uuid,jsonb,integer) to service_role;

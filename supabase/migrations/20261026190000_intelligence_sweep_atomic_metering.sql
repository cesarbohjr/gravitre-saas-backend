-- Atomic subscription-period usage admission. Server controls plan allowance.
create table if not exists public.intelligence_sweep_usage_ledger (
 org_id uuid not null references public.organizations(id) on delete cascade,
 sweep_id uuid not null references public.intelligence_overview_sweeps(id) on delete cascade,
 subscription_period text not null,
 units integer not null default 1 check (units=1),
 state text not null default 'reserved' check (state in ('reserved','settled','released')),
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 primary key(org_id,sweep_id)
);
create index if not exists intelligence_sweep_usage_ledger_period_idx
 on public.intelligence_sweep_usage_ledger(org_id,subscription_period,state);
alter table public.intelligence_sweep_usage_ledger enable row level security;
revoke all on public.intelligence_sweep_usage_ledger from anon,authenticated;
-- Revoke legacy non-metered service admission so it cannot bypass usage charges.
revoke execute on function public.admit_intelligence_overview_sweep(uuid,uuid,jsonb,integer) from service_role;

create or replace function public.admit_metered_intelligence_sweep(
 p_org_id uuid,p_requested_by uuid,p_scope jsonb,p_period text,p_limit integer
) returns public.intelligence_overview_sweeps
language plpgsql security definer set search_path=public
as $$
declare
 result_row public.intelligence_overview_sweeps;
 used_units integer;
begin
 if auth.role() <> 'service_role' then
   raise exception 'service role required' using errcode='42501';
 end if;
 if p_limit < 1 or p_limit > 100000 or p_period !~ '^[0-9]{4}-[0-9]{2}$' then
   raise exception 'invalid entitlement parameters' using errcode='22023';
 end if;
 perform pg_advisory_xact_lock(hashtextextended(p_org_id::text,612009));
 select * into result_row from public.intelligence_overview_sweeps
  where org_id=p_org_id and status in ('queued','running')
  order by created_at desc limit 1;
 if found then return result_row; end if;
 select coalesce(sum(units),0) into used_units
  from public.intelligence_sweep_usage_ledger
  where org_id=p_org_id and subscription_period=p_period and state in ('reserved','settled');
 if used_units >= p_limit then
   raise exception 'intelligence sweep entitlement exceeded' using errcode='P0001';
 end if;
 insert into public.intelligence_overview_sweeps(org_id,requested_by,scope,status)
  values(p_org_id,p_requested_by,coalesce(p_scope,'{}'::jsonb),'queued')
  returning * into result_row;
 insert into public.intelligence_sweep_usage_ledger
  (org_id,sweep_id,subscription_period,units,state)
  values(p_org_id,result_row.id,p_period,1,'reserved');
 return result_row;
end;
$$;
revoke all on function public.admit_metered_intelligence_sweep(uuid,uuid,jsonb,text,integer) from public,anon,authenticated;
grant execute on function public.admit_metered_intelligence_sweep(uuid,uuid,jsonb,text,integer) to service_role;

create or replace function public.settle_intelligence_sweep_unit(
 p_org_id uuid,p_sweep_id uuid,p_state text
) returns boolean language plpgsql security definer set search_path=public
as $$
declare updated_count integer;
begin
 if auth.role() <> 'service_role' then
   raise exception 'service role required' using errcode='42501';
 end if;
 if p_state not in ('settled','released') then
   raise exception 'invalid settlement' using errcode='22023';
 end if;
 update public.intelligence_sweep_usage_ledger set state=p_state,updated_at=now()
  where org_id=p_org_id and sweep_id=p_sweep_id and state='reserved'
   and exists(select 1 from public.intelligence_overview_sweeps s
     where s.org_id=p_org_id and s.id=p_sweep_id
       and s.status in ('partial','completed','failed'));
 get diagnostics updated_count=row_count;
 return updated_count=1;
end;
$$;
revoke all on function public.settle_intelligence_sweep_unit(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.settle_intelligence_sweep_unit(uuid,uuid,text) to service_role;

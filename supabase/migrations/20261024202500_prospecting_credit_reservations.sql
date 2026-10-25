-- Atomic, tenant-scoped free-credit reservations. Server-only RPCs.
create table if not exists public.prospect_provider_budgets (
 org_id uuid not null references public.organizations(id) on delete cascade,
 provider text not null check(provider in ('hunter','emailable','apollo','snov','millionverifier')),
 billing_period date not null,
 free_credit_cap integer not null default 0 check(free_credit_cap>=0),
 enabled boolean not null default false,
 primary key(org_id,provider,billing_period)
);
alter table public.prospect_provider_budgets enable row level security;
revoke all on public.prospect_provider_budgets from anon,authenticated;
revoke all on public.prospect_provider_usage from anon,authenticated;
create or replace function public.prospect_reserve_credits(
 p_org uuid,p_provider text,p_period date,p_request text,p_cost integer
) returns boolean language plpgsql security definer set search_path=public as $$
declare b public.prospect_provider_budgets%rowtype; spent bigint;
begin
 if auth.role() <> 'service_role' or p_cost<=0 or p_request='' or p_provider not in ('hunter','emailable','apollo','snov','millionverifier') then
  raise exception 'credit reservation denied' using errcode='42501';
 end if;
 select * into b from public.prospect_provider_budgets
 where org_id=p_org and provider=p_provider and billing_period=p_period for update;
 if not found or not b.enabled then return false; end if;
 if exists(select 1 from public.prospect_provider_usage where org_id=p_org and provider=p_provider and request_id=p_request) then return false; end if;
 select coalesce(sum(credits_reserved),0) into spent from public.prospect_provider_usage
 where org_id=p_org and provider=p_provider and billing_period=p_period and status in ('reserved','charged');
 if spent+p_cost>b.free_credit_cap then return false; end if;
 insert into public.prospect_provider_usage(org_id,provider,operation,billing_period,request_id,credits_reserved,status)
 values(p_org,p_provider,'verify_or_enrich',p_period,p_request,p_cost,'reserved');
 return true;
end $$;
create or replace function public.prospect_settle_credits(
 p_org uuid,p_provider text,p_request text,p_consumed integer,p_status text
) returns boolean language plpgsql security definer set search_path=public as $$
declare current_row public.prospect_provider_usage%rowtype;
begin
 if auth.role()<>'service_role' or p_status not in ('charged','released','failed') or p_consumed<0 then
  raise exception 'credit settlement denied' using errcode='42501';
 end if;
 select * into current_row from public.prospect_provider_usage
 where org_id=p_org and provider=p_provider and request_id=p_request for update;
 if not found or current_row.status<>'reserved' or p_consumed>current_row.credits_reserved then return false; end if;
 update public.prospect_provider_usage set status=p_status,credits_consumed=p_consumed
 where id=current_row.id;
 return true;
end $$;
revoke all on function public.prospect_reserve_credits(uuid,text,date,text,integer) from public,anon,authenticated;
revoke all on function public.prospect_settle_credits(uuid,text,text,integer,text) from public,anon,authenticated;
grant execute on function public.prospect_reserve_credits(uuid,text,date,text,integer) to service_role;
grant execute on function public.prospect_settle_credits(uuid,text,text,integer,text) to service_role;

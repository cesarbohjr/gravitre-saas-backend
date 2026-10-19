-- Expand-only billing safety. Service-role writes; founder API reads.
alter table public.org_promotional_grants
  add column if not exists max_promotion_value_cents integer not null default 0 check (max_promotion_value_cents >= 0),
  add column if not exists trial_units_reserved jsonb not null default '{}'::jsonb;
alter table public.subscriptions
  add column if not exists voice_auto_topup_monthly_cap_cents integer not null default 3600 check (voice_auto_topup_monthly_cap_cents >= 0);
alter table public.billing_topup_events add column if not exists stripe_customer_id text;
create unique index if not exists billing_topup_events_payment_intent_unique
  on public.billing_topup_events(stripe_payment_intent_id)
  where nullif(stripe_payment_intent_id,'') is not null;

create table if not exists public.billing_safety_alerts (
  id uuid primary key default gen_random_uuid(), dedupe_key text not null unique,
  org_id uuid references public.organizations(id) on delete cascade,
  kind text not null, details jsonb not null default '{}'::jsonb,
  occurrences integer not null default 1, resolved_at timestamptz,
  first_seen_at timestamptz not null default now(), last_seen_at timestamptz not null default now()
);
create table if not exists public.billing_reconciliation_runs (
  run_key text primary key, status text not null check (status in ('running','completed','failed')),
  summary jsonb not null default '{}'::jsonb, started_at timestamptz not null default now(), completed_at timestamptz
);
alter table public.billing_safety_alerts enable row level security;
alter table public.billing_reconciliation_runs enable row level security;
revoke all on public.billing_safety_alerts,public.billing_reconciliation_runs from public,anon,authenticated;
grant select,insert,update on public.billing_safety_alerts,public.billing_reconciliation_runs to service_role;

create or replace function public.record_billing_safety_alert(p_key text,p_org_id uuid,p_kind text,p_details jsonb)
returns void language sql security invoker set search_path=public,pg_temp as $$
  insert into public.billing_safety_alerts(dedupe_key,org_id,kind,details)
  values(p_key,p_org_id,p_kind,p_details)
  on conflict(dedupe_key) do update set occurrences=billing_safety_alerts.occurrences+1,
    details=excluded.details,last_seen_at=now(),resolved_at=null;
$$;

-- Conservative admission reservations are separate from billable usage. Failed
-- provider calls do not release capacity: ambiguous outcomes cannot spend twice.
create or replace function public.reserve_founder_trial_units(p_org_id uuid,p_metric text,p_units integer,p_limit integer)
returns text language plpgsql security invoker set search_path=public,pg_temp as $$
declare g public.org_promotional_grants; b public.org_billing; used bigint;
begin
  if p_metric not in ('ai_credits','voice_minutes','research_lookups') or p_units<=0 or p_limit<0 then
    raise exception 'Invalid trial quota'; end if;
  select * into b from public.org_billing where org_id=p_org_id;
  if not found or b.billing_status<>'trialing' then return 'not_trial'; end if;
  select * into g from public.org_promotional_grants where org_id=p_org_id
    and offer_type='trial' and (status='redeemed' or (status='available' and checkout_attempt_id is not null))
    order by created_at desc limit 1 for update;
  if not found then return 'not_trial'; end if;
  if b.current_period_end is null or b.current_period_end<=now() then raise exception 'Trial expired'; end if;
  used=coalesce((g.trial_units_reserved->>p_metric)::bigint,0);
  if used+p_units>p_limit then raise exception 'Trial quota reached'; end if;
  update public.org_promotional_grants set trial_units_reserved=jsonb_set(trial_units_reserved,array[p_metric],to_jsonb(used+p_units)),updated_at=now() where id=g.id;
  return 'reserved';
end $$;

-- Row lock, live remaining allowance, a pending-charge barrier and monthly cap
-- fence concurrent auto-topups. A pending attempt is never automatically retried.
create or replace function public.claim_voice_auto_topup(p_org_id uuid,p_minutes integer,p_amount integer,p_included integer)
returns jsonb language plpgsql security invoker set search_path=public,pg_temp as $$
declare s public.subscriptions; b public.org_billing; used bigint; spent bigint; e public.billing_topup_events;
begin
  select * into s from public.subscriptions where org_id=p_org_id for update;
  if not found or s.status<>'active' or not s.voice_enabled or not s.voice_auto_topup_enabled then return null; end if;
  select * into b from public.org_billing where org_id=p_org_id;
  if not found or b.billing_status<>'active' or nullif(b.stripe_customer_id,'') is null or nullif(b.stripe_subscription_id,'') is null then return null; end if;
  if p_minutes<>s.voice_auto_topup_minutes or p_minutes<=0 or p_amount<50
    or p_amount>least(s.voice_auto_topup_max_charge_cents,12000) then raise exception 'Topup charge exceeds approved cap'; end if;
  select coalesce(sum(quantity),0) into used from public.usage_records where org_id=p_org_id and metric_type='voice_minutes'
    and recorded_at>=date_trunc('month',now() at time zone 'UTC') at time zone 'UTC';
  if greatest(p_included+s.voice_minutes_prepaid-used,0)>s.voice_auto_topup_threshold_minutes then return null; end if;
  if exists(select 1 from public.billing_topup_events where org_id=p_org_id and source='auto' and status='pending') then return null; end if;
  select coalesce(sum(amount_cents),0) into spent from public.billing_topup_events where org_id=p_org_id and source='auto'
    and status in ('pending','completed') and created_at>=date_trunc('month',now() at time zone 'UTC') at time zone 'UTC';
  if spent+p_amount>s.voice_auto_topup_monthly_cap_cents then return null; end if;
  insert into public.billing_topup_events(org_id,metric_type,minutes,amount_cents,source,status,stripe_customer_id)
    values(p_org_id,'voice_minutes',p_minutes,p_amount,'auto','pending',b.stripe_customer_id) returning * into e;
  return to_jsonb(e)||jsonb_build_object('stripe_subscription_id',b.stripe_subscription_id);
end $$;

-- Exactly-once credit, in the same transaction as payment completion. Never
-- trust minutes or prices in checkout metadata; the stored pending event wins.
create or replace function public.complete_voice_topup(p_event_id uuid,p_org_id uuid,p_customer text,p_amount integer,p_currency text,p_payment_intent text,p_session text)
returns jsonb language plpgsql security invoker set search_path=public,pg_temp as $$
declare e public.billing_topup_events; prepaid integer;
begin
  select * into e from public.billing_topup_events where id=p_event_id and org_id=p_org_id for update;
  if not found or e.stripe_customer_id is distinct from p_customer or e.amount_cents<>p_amount or e.currency<>p_currency
    or nullif(p_payment_intent,'') is null or (e.stripe_checkout_session_id is not null and e.stripe_checkout_session_id is distinct from nullif(p_session,'')) then
    raise exception 'Topup payment identity mismatch'; end if;
  if e.status='completed' then
    if e.stripe_payment_intent_id is distinct from p_payment_intent then raise exception 'Topup payment changed'; end if;
    return jsonb_build_object('org_id',p_org_id,'minutes',e.minutes,'already_completed',true);
  end if;
  if e.status<>'pending' then raise exception 'Topup is not pending'; end if;
  update public.subscriptions set voice_minutes_prepaid=voice_minutes_prepaid+e.minutes where org_id=p_org_id returning voice_minutes_prepaid into prepaid;
  if not found then raise exception 'Subscription missing'; end if;
  update public.billing_topup_events set status='completed',completed_at=now(),stripe_payment_intent_id=p_payment_intent,
    stripe_checkout_session_id=coalesce(stripe_checkout_session_id,nullif(p_session,'')) where id=e.id;
  return jsonb_build_object('org_id',p_org_id,'minutes',e.minutes,'voice_minutes_prepaid',prepaid);
end $$;
revoke all on function public.record_billing_safety_alert(text,uuid,text,jsonb),public.reserve_founder_trial_units(uuid,text,integer,integer),public.claim_voice_auto_topup(uuid,integer,integer,integer),public.complete_voice_topup(uuid,uuid,text,integer,text,text,text) from public,anon,authenticated;
grant execute on function public.record_billing_safety_alert(text,uuid,text,jsonb),public.reserve_founder_trial_units(uuid,text,integer,integer),public.claim_voice_auto_topup(uuid,integer,integer,integer),public.complete_voice_topup(uuid,uuid,text,integer,text,text,text) to service_role;

-- Customer identity is independent of a temporary promotional offer.
-- All writes go through service-role-only, platform-admin endpoints.
create table if not exists public.org_commercial_profiles (
  org_id uuid primary key references public.organizations(id) on delete cascade,
  customer_category text not null default 'unreviewed'
    check (customer_category in ('unreviewed','external','internal','test')),
  classification_reason text,
  classified_by uuid,
  classified_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table if not exists public.org_promotional_grants (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations(id) on delete cascade,
  offer_type text not null check (offer_type in ('trial','discount')),
  trial_days integer check (trial_days between 1 and 90),
  stripe_coupon_id text,
  percent_off numeric(5,2) check (percent_off > 0 and percent_off <= 100),
  discount_months integer check (discount_months between 1 and 12),
  status text not null default 'available'
    check (status in ('available','redeemed','revoked','expired')),
  valid_until timestamptz,
  redeemed_at timestamptz,
  stripe_subscription_id text,
  created_by uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (offer_type = 'trial' and trial_days is not null and stripe_coupon_id is null and percent_off is null and discount_months is null)
    or (offer_type = 'discount' and trial_days is null and nullif(stripe_coupon_id, '') is not null and percent_off is not null and discount_months is not null)
  )
);
create unique index if not exists org_promotional_grants_one_available
  on public.org_promotional_grants (org_id) where status = 'available';
create index if not exists org_promotional_grants_org_history
  on public.org_promotional_grants (org_id, created_at desc);
alter table public.org_commercial_profiles enable row level security;
alter table public.org_promotional_grants enable row level security;
revoke all on public.org_commercial_profiles from public, anon, authenticated;
revoke all on public.org_promotional_grants from public, anon, authenticated;
grant select, insert, update on public.org_commercial_profiles to service_role;
grant select, insert, update on public.org_promotional_grants to service_role;
-- No direct browser writes and no customer ability to grant themselves a promotion.

-- Evidence-based classification from the 2026-10-18 Stripe audit.
-- Unknown organizations remain unreviewed, never automatically counted as customers.
-- Seed only if a matching production organization exists; clean local/staging
-- resets have no founder/QA rows and must still apply successfully.
insert into public.org_commercial_profiles (org_id, customer_category, classification_reason)
select source.org_id::uuid, source.customer_category, source.classification_reason
from (values
('cbbf993b-b22f-41ce-964b-1fc25e0dd9ea', 'internal', 'Founder-owned workspace, Stripe reconciliation 2026-10-18'),
('28d91c1f-63e6-4c62-9eb7-519212635b64', 'internal', 'Founder-owned workspace, Stripe reconciliation 2026-10-18'),
('d797d382-8038-456c-ab9e-ac0b750c3a92', 'test', 'click-audit workspace, Stripe reconciliation 2026-10-18'),
('e94447a9-1442-427e-9fef-d3515f302d93', 'test', 'click-audit workspace, Stripe reconciliation 2026-10-18'),
('658c76b3-04b7-489b-bb7e-64a5f3ec1cbe', 'test', 'isolated conversation smoke workspace, Stripe reconciliation 2026-10-18')
) as source(org_id, customer_category, classification_reason)
join public.organizations as org on org.id = source.org_id::uuid
on conflict (org_id) do nothing;
-- A grant is reserved before contacting Stripe. No clock-based reclaim: an
-- ambiguous network failure must not allow a second subscription to be created.
alter table public.org_promotional_grants
  add column if not exists checkout_attempt_id uuid,
  add column if not exists checkout_reserved_at timestamptz,
  add column if not exists checkout_customer_id text,
  add column if not exists checkout_price_id text,
  add column if not exists checkout_user_id uuid;
create unique index if not exists org_promotional_grants_one_redeemed_trial
  on public.org_promotional_grants (org_id)
  where offer_type = 'trial' and status = 'redeemed';

create or replace function public.reserve_founder_checkout(
  p_org_id uuid, p_grant_id uuid, p_customer_id text, p_price_id text, p_user_id uuid
) returns setof public.org_promotional_grants
language plpgsql security invoker set search_path = public, pg_temp as $$
declare g public.org_promotional_grants;
begin
  -- Serialize classification changes, issuance, and all claims for this org.
  perform 1 from public.org_commercial_profiles
    where org_id = p_org_id and customer_category = 'external' for update;
  if not found then raise exception 'Reviewed external organization required'; end if;
  select * into g from public.org_promotional_grants
    where id = p_grant_id and org_id = p_org_id for update;
  if not found or g.status <> 'available'
    or (g.checkout_attempt_id is null and g.valid_until <= now()) then
    raise exception 'Offer unavailable';
  end if;
  if nullif(p_customer_id, '') is null or nullif(p_price_id, '') is null or p_user_id is null then
    raise exception 'Checkout identity required';
  end if;
  if g.offer_type = 'trial' and exists (
    select 1 from public.org_promotional_grants
    where org_id = p_org_id and offer_type = 'trial' and status = 'redeemed'
  ) then raise exception 'Trial already redeemed'; end if;
  if g.checkout_attempt_id is not null then
    if g.checkout_customer_id <> p_customer_id or g.checkout_price_id <> p_price_id
      or g.checkout_user_id <> p_user_id
      or g.checkout_reserved_at < now() - interval '23 hours' then
      raise exception 'Checkout already reserved; reconcile existing session';
    end if;
  else
    update public.org_promotional_grants set checkout_attempt_id = gen_random_uuid(),
      checkout_reserved_at = now(), checkout_customer_id = p_customer_id,
      checkout_price_id = p_price_id, checkout_user_id = p_user_id, updated_at = now()
      where id = p_grant_id returning * into g;
  end if;
  return next g;
end $$;
revoke all on function public.reserve_founder_checkout(uuid,uuid,text,text,uuid) from public, anon, authenticated;
grant execute on function public.reserve_founder_checkout(uuid,uuid,text,text,uuid) to service_role;

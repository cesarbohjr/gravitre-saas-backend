-- Customer identity is independent of a temporary promotional offer.
-- All writes go through service-role-only, platform-admin endpoints.
create table if not exists public.org_commercial_profiles (
  org_id uuid primary key references public.organizations(id) on delete cascade,
  customer_category text not null default 'external'
    check (customer_category in ('external','internal','test')),
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
  status text not null default 'available'
    check (status in ('available','redeemed','revoked','expired')),
  valid_until timestamptz,
  redeemed_at timestamptz,
  stripe_subscription_id text,
  created_by uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (offer_type = 'trial' and trial_days is not null and stripe_coupon_id is null)
    or (offer_type = 'discount' and trial_days is null and nullif(stripe_coupon_id, '') is not null)
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

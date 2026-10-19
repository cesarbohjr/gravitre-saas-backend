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

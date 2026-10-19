-- Public promotion codes (e.g. LAUNCH30 = 30% off) usable by anyone at checkout.
--
-- Stripe is authoritative: every row mirrors a Stripe PromotionCode + Coupon the
-- platform-admin API created, and Stripe validates and applies the discount at
-- checkout. These tables are the admin catalog plus redemption evidence. They
-- are independent of founder offers (org_promotional_grants); a founder offer
-- always wins and is never combined with a public code.
--
-- Service-role only: no anon/authenticated grants, RLS enabled with no policies.
-- Idempotent (if not exists / create or replace) and expand-only.
--
-- Rollback (manual; only after confirming no evidence must be kept, Stripe
-- objects are unaffected):
--   drop function if exists public.record_promotion_code_redemption(text, text, uuid, text, jsonb);
--   drop table if exists public.promotion_code_events;
--   drop table if exists public.promotion_codes;

create table if not exists public.promotion_codes (
  id uuid primary key default gen_random_uuid(),
  stripe_promotion_code_id text not null unique,
  stripe_coupon_id text not null,
  -- Customer-facing code, stored upper-case (Stripe codes are case-insensitive).
  code text not null check (code ~ '^[A-Z0-9][A-Z0-9_-]{2,39}$'),
  percent_off numeric(5,2) check (percent_off > 0 and percent_off <= 100),
  amount_off_cents integer check (amount_off_cents > 0),
  currency text check (currency is null or currency ~ '^[a-z]{3}$'),
  duration text not null check (duration in ('once','repeating','forever')),
  duration_in_months integer check (duration_in_months between 1 and 36),
  max_redemptions integer check (max_redemptions > 0),
  expires_at timestamptz,
  first_time_only boolean not null default false,
  -- Empty = every base plan. Enforced in Stripe via Coupon.applies_to products.
  restricted_plan_codes text[] not null default '{}'
    check (restricted_plan_codes <@ array['node','control','command']::text[]),
  active boolean not null default true,
  -- Cached from Stripe PromotionCode.times_redeemed (list refresh) and bumped
  -- once per verified redemption webhook.
  times_redeemed integer not null default 0 check (times_redeemed >= 0),
  redemption_count_synced_at timestamptz,
  created_by uuid,
  deactivated_by uuid,
  deactivated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (percent_off is not null and amount_off_cents is null and currency is null)
    or (percent_off is null and amount_off_cents is not null and currency is not null)
  ),
  check ((duration = 'repeating') = (duration_in_months is not null))
);
create unique index if not exists promotion_codes_one_active_code
  on public.promotion_codes (code) where active;
create index if not exists promotion_codes_created
  on public.promotion_codes (created_at desc);

-- Append-only lifecycle and redemption evidence. dedupe_key makes webhook
-- redelivery and the checkout/invoice double signal count a redemption once.
create table if not exists public.promotion_code_events (
  id uuid primary key default gen_random_uuid(),
  dedupe_key text not null unique,
  promotion_code_id uuid references public.promotion_codes(id) on delete set null,
  stripe_promotion_code_id text,
  event_type text not null check (event_type in ('created','deactivated','redeemed')),
  org_id uuid references public.organizations(id) on delete set null,
  actor_id uuid,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists promotion_code_events_code
  on public.promotion_code_events (promotion_code_id, created_at desc);

alter table public.promotion_codes enable row level security;
alter table public.promotion_code_events enable row level security;
revoke all on public.promotion_codes, public.promotion_code_events from public, anon, authenticated;
grant select, insert, update on public.promotion_codes to service_role;
grant select, insert on public.promotion_code_events to service_role;

-- Exactly-once redemption: insert the evidence row and bump the cached counter
-- in one transaction. Returns false for a duplicate signal.
create or replace function public.record_promotion_code_redemption(
  p_dedupe_key text, p_stripe_promotion_code_id text, p_org_id uuid,
  p_source_event text, p_details jsonb
) returns boolean
language plpgsql security invoker set search_path = public, pg_temp as $$
declare v_code_id uuid; v_inserted uuid;
begin
  if nullif(p_dedupe_key, '') is null or nullif(p_stripe_promotion_code_id, '') is null then
    raise exception 'Redemption identity required';
  end if;
  select id into v_code_id from public.promotion_codes
    where stripe_promotion_code_id = p_stripe_promotion_code_id for update;
  insert into public.promotion_code_events
    (dedupe_key, promotion_code_id, stripe_promotion_code_id, event_type, org_id, details)
  values (p_dedupe_key, v_code_id, p_stripe_promotion_code_id, 'redeemed', p_org_id,
          coalesce(p_details, '{}'::jsonb) || jsonb_build_object('source_event', p_source_event))
  on conflict (dedupe_key) do nothing
  returning id into v_inserted;
  if v_inserted is null then return false; end if;
  if v_code_id is not null then
    update public.promotion_codes
      set times_redeemed = times_redeemed + 1, updated_at = now()
      where id = v_code_id;
  end if;
  return true;
end $$;
revoke all on function public.record_promotion_code_redemption(text, text, uuid, text, jsonb)
  from public, anon, authenticated;
grant execute on function public.record_promotion_code_redemption(text, text, uuid, text, jsonb)
  to service_role;

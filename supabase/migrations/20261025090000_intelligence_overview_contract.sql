-- Intelligence Overview: tenant-wide governed settings and durable analysis requests.
create table if not exists public.intelligence_overview_profiles (
  org_id uuid primary key references public.organizations(id) on delete cascade,
  capabilities jsonb not null default '{}'::jsonb,
  updated_by uuid,
  updated_at timestamptz not null default now(),
  constraint overview_capabilities_object check (jsonb_typeof(capabilities) = 'object')
);
create table if not exists public.intelligence_overview_sweeps (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations(id) on delete cascade,
  requested_by uuid,
  status text not null default 'queued' check (status in ('queued','running','completed','partial','failed','cancelled')),
  scope jsonb not null default '{}'::jsonb,
  results jsonb not null default '{}'::jsonb,
  error_code text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz
);
create index if not exists intelligence_overview_sweeps_org_created_idx on public.intelligence_overview_sweeps(org_id, created_at desc);
alter table public.intelligence_overview_profiles enable row level security;
alter table public.intelligence_overview_sweeps enable row level security;
-- Backend service-role access only; application-layer membership/role checks mandatory.
revoke all on public.intelligence_overview_profiles from anon, authenticated;
revoke all on public.intelligence_overview_sweeps from anon, authenticated;

-- One active sweep per tenant, enforced atomically even across API workers.
create unique index if not exists intelligence_overview_sweeps_one_active_org_idx
on public.intelligence_overview_sweeps(org_id) where status in ('queued', 'running');

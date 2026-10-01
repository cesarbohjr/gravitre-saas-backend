-- Slice 1: tenant Play installations and Play-run orchestration records.
-- Plays compose canonical workflows; these tables do not introduce a second execution engine.

create table if not exists public.play_installations (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations(id) on delete cascade,
  play_key text not null,
  play_version text not null,
  environment_name text not null default 'production',
  goal_id uuid null references public.goals(id) on delete set null,
  operating_mode text not null default 'OBSERVE'
    check (operating_mode in ('OBSERVE','RECOMMEND','ACT WITH APPROVAL','ACT WITHIN POLICY')),
  status text not null default 'draft'
    check (status in ('draft','ready','active','paused','archived')),
  configuration jsonb not null default '{}'::jsonb,
  created_by uuid null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (org_id, environment_name, play_key)
);

create index if not exists play_installations_org_idx
  on public.play_installations (org_id, environment_name, status);

create table if not exists public.play_runs (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations(id) on delete cascade,
  installation_id uuid not null references public.play_installations(id) on delete cascade,
  play_key text not null,
  play_version text not null,
  operating_mode text not null,
  trigger_type text not null default 'manual',
  status text not null default 'pending'
    check (status in ('pending','running','awaiting_approval','completed','partial_success','failed','cancelled')),
  workflow_run_ids uuid[] not null default '{}'::uuid[],
  started_at timestamptz null,
  completed_at timestamptz null,
  created_by uuid null,
  created_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists play_runs_org_installation_idx
  on public.play_runs (org_id, installation_id, created_at desc);

alter table public.play_installations enable row level security;
alter table public.play_runs enable row level security;

drop policy if exists play_installations_org_scope on public.play_installations;
create policy play_installations_org_scope on public.play_installations
  for all using (org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()))
  with check (org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()));

drop policy if exists play_runs_org_scope on public.play_runs;
create policy play_runs_org_scope on public.play_runs
  for all using (org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()))
  with check (org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()));

comment on table public.play_installations is
  'Tenant configuration for a versioned Play definition. Execution remains in canonical workflow runtime.';
comment on table public.play_runs is
  'Orchestration record that groups canonical workflow runs under a Play installation; not an execution engine.';

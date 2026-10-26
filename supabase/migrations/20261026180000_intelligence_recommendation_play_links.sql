-- Recommendation-to-Play attribution. The canonical Play/workflow runtime
-- remains the only authority to approve and execute connector writes.
create table if not exists public.intelligence_recommendation_play_links (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations(id) on delete cascade,
  recommendation_id text not null,
  installation_id uuid not null,
  play_key text not null,
  play_run_id uuid,
  workflow_run_ids jsonb not null default '[]'::jsonb,
  status text not null default 'submitting'
    check (status in ('submitting','submitted','rejected','handoff_error')),
  created_by uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint recommendation_play_link_unique unique (org_id, recommendation_id, installation_id)
);
create index if not exists intelligence_recommendation_play_links_org_run_idx
on public.intelligence_recommendation_play_links(org_id, play_run_id);
alter table public.intelligence_recommendation_play_links enable row level security;
revoke all on public.intelligence_recommendation_play_links from anon, authenticated;

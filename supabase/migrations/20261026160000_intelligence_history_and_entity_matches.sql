-- Offline-ready historical intelligence ingestion and scoped identity observations.
-- Only service-role backend reads/writes; no implicit user grants.
create table if not exists public.intelligence_history_checkpoints (
  org_id uuid not null references public.organizations(id) on delete cascade,
  connector_id uuid not null,
  provider text not null,
  object_type text not null,
  cursor jsonb not null default '{}'::jsonb,
  state text not null default 'idle' check (state in ('idle','running','complete','failed')),
  completed_at timestamptz,
  updated_at timestamptz not null default now(),
  primary key (org_id, connector_id, object_type)
);
create table if not exists public.intelligence_history_records (
  org_id uuid not null references public.organizations(id) on delete cascade,
  connector_id uuid not null,
  provider text not null,
  object_type text not null,
  external_id text not null,
  observed_at timestamptz not null,
  source_updated_at timestamptz,
  record jsonb not null,
  normalized_identity jsonb not null default '{}'::jsonb,
  deleted_at timestamptz,
  primary key (org_id, connector_id, object_type, external_id),
  constraint intelligence_history_external_id_not_blank check (length(trim(external_id)) > 0)
);
create index if not exists intelligence_history_records_org_type_time_idx
  on public.intelligence_history_records(org_id, object_type, observed_at desc);
create table if not exists public.intelligence_entity_matches (
  org_id uuid not null references public.organizations(id) on delete cascade,
  identity_kind text not null,
  identity_hash text not null,
  match_status text not null check (match_status in ('verified_key','candidate','conflict')),
  record_references jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (org_id, identity_kind, identity_hash)
);
alter table public.intelligence_history_checkpoints enable row level security;
alter table public.intelligence_history_records enable row level security;
alter table public.intelligence_entity_matches enable row level security;
revoke all on public.intelligence_history_checkpoints from anon, authenticated;
revoke all on public.intelligence_history_records from anon, authenticated;
revoke all on public.intelligence_entity_matches from anon, authenticated;

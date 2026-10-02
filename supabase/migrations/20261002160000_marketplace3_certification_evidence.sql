-- Marketplace 3.0 certification evidence.
-- Raw evidence is intentionally backend-only: RLS is enabled and no authenticated
-- policies are created. Admin/platform-admin APIs expose only governed summaries.

create table if not exists public.marketplace_certification_evidence (
  id uuid primary key default gen_random_uuid(),
  asset_id uuid not null references public.marketplace_assets(id) on delete cascade,
  asset_version integer not null check (asset_version > 0),
  org_id uuid null references public.organizations(id) on delete cascade,
  evidence_kind text not null
    check (evidence_kind in ('runtime', 'outcome')),
  provider text null,
  environment text not null default 'production',
  evidence_ref text not null,
  verified_actions jsonb not null default '[]'::jsonb,
  verified_outcome_events jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_by uuid null references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (asset_id, asset_version, evidence_ref)
);

create index if not exists marketplace_certification_evidence_asset_version_idx
  on public.marketplace_certification_evidence (asset_id, asset_version, created_at desc);

create index if not exists marketplace_certification_evidence_org_idx
  on public.marketplace_certification_evidence (org_id, created_at desc)
  where org_id is not null;

alter table public.marketplace_certification_evidence enable row level security;

comment on table public.marketplace_certification_evidence is
  'Immutable evidence references used to certify Marketplace 3.0 Outcome Packs. Raw evidence is backend/admin-only.';
comment on column public.marketplace_certification_evidence.evidence_ref is
  'Reference to external or Gravitre verification proof; the Marketplace never treats config claims as evidence.';

-- Immutable external-write approval reference, accessible to service role only.
create table if not exists public.prospect_action_approvals (
 id uuid primary key default gen_random_uuid(),
 org_id uuid not null,
 run_id uuid not null,
 actor_id uuid not null,
 stage text not null,
 action text not null,
 payload_hash text not null check (length(payload_hash)=64),
 pending_action_id text not null,
 status text not null default 'awaiting_user'
   check(status in ('awaiting_user','approved','rejected','expired','consumed')),
 reviewed_by uuid,
 reviewed_at timestamptz,
 created_at timestamptz not null default now(),
 foreign key(org_id,run_id) references public.prospect_play_runs(org_id,id) on delete cascade,
 unique(org_id,run_id,stage,action,payload_hash)
);
alter table public.prospect_action_approvals enable row level security;
revoke all on public.prospect_action_approvals from anon,authenticated;
-- All approvals must be inserted/updated by the trusted application review service.
create index if not exists prospect_approval_exact_lookup on public.prospect_action_approvals
 (org_id,actor_id,run_id,stage,action,payload_hash,status);

-- Transaction-safe prospecting state with tenant-scoped durable execution history.
create table if not exists public.prospect_play_runs (
 id uuid primary key default gen_random_uuid(),
 org_id uuid not null references public.organizations(id) on delete cascade,
 requested_by uuid not null,
 state text not null default 'created' check (state in
 ('created','running','awaiting_review','awaiting_approval','completed','failed','cancelled')),
 current_stage text not null default 'discover',
 request_key text not null,
 last_error text,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(org_id,request_key),
 unique(org_id,id)
);
create table if not exists public.prospect_play_steps (
 id uuid primary key default gen_random_uuid(),
 org_id uuid not null,
 run_id uuid not null,
 stage text not null check(stage in
 ('discover','research','enrich','verify','consent_review','stage','crm_export','outreach_enroll','delivery_sync')),
 status text not null default 'pending' check(status in
 ('pending','running','awaiting_approval','succeeded','failed','outcome_unknown')),
 attempt integer not null default 0,
 evidence jsonb not null default '{}'::jsonb,
 last_error text,
 updated_at timestamptz not null default now(),
 unique(org_id,run_id,stage),
 foreign key(org_id,run_id) references public.prospect_play_runs(org_id,id) on delete cascade
);
create table if not exists public.prospect_outreach_events (
 id uuid primary key default gen_random_uuid(),
 org_id uuid not null references public.organizations(id) on delete cascade,
 provider text not null,
 provider_event_id text not null,
 provider_lead_id text,
 event_type text not null check(event_type in
 ('sent','delivered','bounced','replied','unsubscribed','complained','failed')),
 payload jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 unique(org_id,provider,provider_event_id)
);
do $$ begin
 if not exists (select 1 from pg_constraint where conname='prospect_play_steps_org_run_fkey') then
  null;
 end if;
end $$;
alter table public.prospect_play_runs enable row level security;
alter table public.prospect_play_steps enable row level security;
alter table public.prospect_outreach_events enable row level security;
create policy prospect_runs_member_read on public.prospect_play_runs for select
 using(org_id in(select org_id from public.organization_members where user_id=auth.uid()));
create policy prospect_steps_member_read on public.prospect_play_steps for select
 using(org_id in(select org_id from public.organization_members where user_id=auth.uid()));
create policy prospect_events_member_read on public.prospect_outreach_events for select
 using(org_id in(select org_id from public.organization_members where user_id=auth.uid()));
revoke insert,update,delete on public.prospect_play_runs,public.prospect_play_steps,public.prospect_outreach_events from anon,authenticated;

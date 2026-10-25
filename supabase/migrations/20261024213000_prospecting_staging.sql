-- Durable staging for the Qualified Prospecting Play; does not write to CRM.
create table if not exists public.prospect_staging (
 id uuid primary key default gen_random_uuid(),
 org_id uuid not null references public.organizations(id) on delete cascade,
 contact_id uuid not null,
 requested_by uuid not null,
 source_play_run_id uuid,
 status text not null default 'pending_approval'
   check(status in ('pending_approval','approved','rejected','exported','cancelled')),
 approval_action_id text,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(org_id,contact_id),
 foreign key(org_id,contact_id) references public.prospect_contacts(org_id,id) on delete cascade
);
alter table public.prospect_staging enable row level security;
drop policy if exists prospect_staging_org_member_read on public.prospect_staging;
create policy prospect_staging_org_member_read on public.prospect_staging for select
 using(org_id in(select org_id from public.organization_members where user_id=auth.uid()));
revoke insert,update,delete on public.prospect_staging from anon,authenticated;
-- Export happens only via canonical PendingAction and a verified role-scoped service path.

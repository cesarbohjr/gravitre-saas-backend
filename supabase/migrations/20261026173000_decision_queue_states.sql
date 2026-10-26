-- Decision queue: per-request snooze, delegation and edit record for pending approvals.
-- One row per (org, approval id). The approval id is a workflow_runs.id or an approvals.id,
-- so it is stored as text with no foreign key. Writes go through the API (service role) only.
create table if not exists public.decision_queue_states (
 id uuid primary key default gen_random_uuid(),
 org_id uuid not null references public.organizations(id) on delete cascade,
 approval_id text not null,
 snoozed_until timestamptz,
 snoozed_by uuid,
 delegated_to uuid,
 delegated_by uuid,
 delegated_at timestamptz,
 delegate_note text check (delegate_note is null or char_length(delegate_note) <= 500),
 edited_by uuid,
 edited_at timestamptz,
 original_parameters jsonb,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(org_id, approval_id)
);
create index if not exists decision_queue_states_delegated_idx
 on public.decision_queue_states(org_id, delegated_to) where delegated_to is not null;
alter table public.decision_queue_states enable row level security;
drop policy if exists decision_queue_states_org_member_read on public.decision_queue_states;
create policy decision_queue_states_org_member_read on public.decision_queue_states for select
 using(org_id in(select org_id from public.organization_members where user_id=auth.uid()));
revoke insert,update,delete on public.decision_queue_states from anon,authenticated;

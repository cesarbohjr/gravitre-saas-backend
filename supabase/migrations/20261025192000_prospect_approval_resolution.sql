-- Approval must be independently persisted and bound to exact run, stage and actor.
create table if not exists public.prospect_stage_approvals (
 id uuid primary key default gen_random_uuid(),
 org_id uuid not null,
 run_id uuid not null,
 stage text not null check (stage in ('consent_review','stage','crm_export','outreach_enroll')),
 actor_id uuid not null,
 payload_sha256 text not null check(length(payload_sha256)=64),
 state text not null default 'awaiting_user' check(state in('awaiting_user','confirmed','declined','expired')),
 approved_by uuid,
 approved_at timestamptz,
 created_at timestamptz not null default now(),
 unique(org_id,run_id,stage,payload_sha256),
 foreign key(org_id,run_id) references public.prospect_play_runs(org_id,id) on delete cascade
);
alter table public.prospect_stage_approvals enable row level security;
create policy prospect_approvals_member_read on public.prospect_stage_approvals for select
 using(org_id in (select org_id from public.organization_members where user_id=auth.uid()));
revoke insert,update,delete on public.prospect_stage_approvals from anon,authenticated;
create or replace function public.prospect_stage_approval_verified(
 p_org uuid,p_run uuid,p_stage text,p_actor uuid,p_digest text
) returns boolean language sql stable security definer set search_path=public as $$
 select auth.role()='service_role' and exists (
 select 1 from public.prospect_stage_approvals
 where org_id=p_org and run_id=p_run and stage=p_stage and actor_id=p_actor
 and payload_sha256=p_digest and state='confirmed' and approved_by is not null and approved_at is not null
 );
$$;
revoke all on function public.prospect_stage_approval_verified(uuid,uuid,text,uuid,text) from public,anon,authenticated;
grant execute on function public.prospect_stage_approval_verified(uuid,uuid,text,uuid,text) to service_role;

-- Atomic stage claim prevents two workers executing a prospecting step concurrently.
create or replace function public.prospect_claim_step(
 p_org uuid,p_run uuid,p_stage text,p_actor uuid
) returns boolean language plpgsql security definer set search_path=public as $$
declare v_state text; v_stage text; v_existing text;
begin
 if auth.role() <> 'service_role' then raise exception 'forbidden'; end if;
 select state,current_stage into v_state,v_stage from prospect_play_runs
  where org_id=p_org and id=p_run and requested_by=p_actor for update;
 if not found or v_state not in ('created','running','awaiting_approval') or v_stage<>p_stage then return false; end if;
 select status into v_existing from prospect_play_steps
  where org_id=p_org and run_id=p_run and stage=p_stage for update;
 if v_existing is not null and v_existing not in ('pending','failed','awaiting_approval') then return false; end if;
 insert into prospect_play_steps(org_id,run_id,stage,status,attempt)
 values(p_org,p_run,p_stage,'running',1)
 on conflict(org_id,run_id,stage) do update
 set status='running',attempt=prospect_play_steps.attempt+1,updated_at=now();
 update prospect_play_runs set state='running',updated_at=now() where org_id=p_org and id=p_run;
 return true;
end $$;
revoke all on function public.prospect_claim_step(uuid,uuid,text,uuid) from public,anon,authenticated;
grant execute on function public.prospect_claim_step(uuid,uuid,text,uuid) to service_role;

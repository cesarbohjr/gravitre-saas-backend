-- Claim completion is an atomic transaction, guarding against stale workers.
create or replace function public.prospect_finish_step(
 p_org uuid,p_run uuid,p_stage text,p_actor uuid,p_next text,p_evidence jsonb
) returns boolean language plpgsql security definer set search_path=public as $$
declare v_state text; v_stage text; v_status text;
begin
 if auth.role()<>'service_role' then raise exception 'forbidden'; end if;
 select state,current_stage into v_state,v_stage from public.prospect_play_runs
 where org_id=p_org and id=p_run and requested_by=p_actor for update;
 if not found or v_state<>'running' or v_stage<>p_stage then return false; end if;
 select status into v_status from public.prospect_play_steps
 where org_id=p_org and run_id=p_run and stage=p_stage for update;
 if v_status<>'running' then return false; end if;
 update public.prospect_play_steps set status='succeeded',
 evidence=coalesce(p_evidence,'{}'::jsonb),updated_at=now()
 where org_id=p_org and run_id=p_run and stage=p_stage;
 update public.prospect_play_runs set current_stage=p_next,
 state=case when p_next='completed' then 'completed' else 'running' end,
 updated_at=now() where org_id=p_org and id=p_run;
 return true;
end $$;
revoke all on function public.prospect_finish_step(uuid,uuid,text,uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.prospect_finish_step(uuid,uuid,text,uuid,text,jsonb) to service_role;

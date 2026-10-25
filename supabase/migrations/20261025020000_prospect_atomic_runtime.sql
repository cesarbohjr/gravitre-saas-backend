-- Service-role-only atomic checkpoints. Fail closed on concurrent claims.
create or replace function public.prospect_claim_step(p_org uuid,p_run uuid,p_stage text,p_actor uuid)
returns boolean language plpgsql security definer set search_path=public as $$
declare v_run public.prospect_play_runs%rowtype; v_status text;
begin
 if auth.role() <> 'service_role' then raise exception 'service role required' using errcode='42501'; end if;
 select * into v_run from public.prospect_play_runs where org_id=p_org and id=p_run for update;
 if not found or v_run.requested_by<>p_actor or v_run.current_stage<>p_stage
   or v_run.state not in ('created','running','awaiting_approval') then return false; end if;
 select status into v_status from public.prospect_play_steps where org_id=p_org and run_id=p_run and stage=p_stage for update;
 if v_status is not null and v_status not in ('pending','awaiting_approval') then return false; end if;
 insert into public.prospect_play_steps(org_id,run_id,stage,status,attempt)
 values(p_org,p_run,p_stage,'running',1)
 on conflict(org_id,run_id,stage) do update
 set status='running', attempt=prospect_play_steps.attempt+1,updated_at=now();
 update public.prospect_play_runs set state='running',updated_at=now() where id=p_run and org_id=p_org;
 return true;
end $$;
create or replace function public.prospect_finish_step(p_org uuid,p_run uuid,p_stage text,p_actor uuid,p_next text,p_evidence jsonb)
returns boolean language plpgsql security definer set search_path=public as $$
declare v_run public.prospect_play_runs%rowtype; v_status text;
begin
 if auth.role()<>'service_role' then raise exception 'service role required' using errcode='42501'; end if;
 select * into v_run from public.prospect_play_runs where org_id=p_org and id=p_run for update;
 if not found or v_run.requested_by<>p_actor or v_run.current_stage<>p_stage then return false; end if;
 select status into v_status from public.prospect_play_steps where org_id=p_org and run_id=p_run and stage=p_stage for update;
 if v_status is distinct from 'running' then return false; end if;
 update public.prospect_play_steps set status='succeeded',evidence=p_evidence,updated_at=now()
 where org_id=p_org and run_id=p_run and stage=p_stage;
 update public.prospect_play_runs set current_stage=p_next,
 state=case when p_next='completed' then 'completed' else 'running' end,updated_at=now()
 where org_id=p_org and id=p_run;
 return true;
end $$;
create or replace function public.prospect_record_delivery_atomic(
 p_org uuid,p_provider text,p_event_id text,p_lead text,p_event_type text,p_email text)
returns boolean language plpgsql security definer set search_path=public as $$
declare v_inserted uuid;
begin
 if auth.role()<>'service_role' then raise exception 'service role required' using errcode='42501'; end if;
 if p_org is null or nullif(p_provider,'') is null or nullif(p_event_id,'') is null
 or nullif(p_lead,'') is null or p_event_type not in
 ('sent','delivered','bounced','replied','unsubscribed','complained','failed') then
 raise exception 'invalid provider delivery event'; end if;
 if p_event_type in ('bounced','unsubscribed','complained') and
 (p_email is null or position('@' in p_email)<2) then raise exception 'suppression requires valid email'; end if;
 insert into public.prospect_outreach_events(org_id,provider,provider_event_id,provider_lead_id,event_type)
 values(p_org,p_provider,p_event_id,p_lead,p_event_type)
 on conflict(org_id,provider,provider_event_id) do nothing returning id into v_inserted;
 if v_inserted is null then return false; end if;
 if p_event_type in ('bounced','unsubscribed','complained') then
 insert into public.prospect_suppressions(org_id,normalized_email,reason)
 values(p_org,lower(trim(p_email)),p_event_type)
 on conflict(org_id,normalized_email) do update set reason=excluded.reason;
 end if;
 return true;
end $$;
revoke all on function public.prospect_claim_step(uuid,uuid,text,uuid) from public,anon,authenticated;
revoke all on function public.prospect_finish_step(uuid,uuid,text,uuid,text,jsonb) from public,anon,authenticated;
revoke all on function public.prospect_record_delivery_atomic(uuid,text,text,text,text,text) from public,anon,authenticated;
grant execute on function public.prospect_claim_step(uuid,uuid,text,uuid) to service_role;
grant execute on function public.prospect_finish_step(uuid,uuid,text,uuid,text,jsonb) to service_role;
grant execute on function public.prospect_record_delivery_atomic(uuid,text,text,text,text,text) to service_role;

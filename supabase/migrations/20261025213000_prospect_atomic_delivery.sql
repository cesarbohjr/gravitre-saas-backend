-- Transactionally deduplicate Smartlead events and apply irreversible suppressions.
-- This service-role RPC is invoked only after authenticated provider event verification.
create or replace function public.prospect_record_delivery_atomic(
 p_org uuid,p_provider text,p_event_id text,p_lead text,
 p_event_type text,p_email text
) returns boolean language plpgsql security definer set search_path=public as $$
declare v_inserted uuid;
begin
 if auth.role()<>'service_role' then raise exception 'forbidden'; end if;
 if p_provider not in ('smartlead','instantly','quickmail','hunter','snov')
   or p_event_type not in ('sent','delivered','bounced','replied','unsubscribed','complained','failed')
   or nullif(trim(p_event_id),'') is null or nullif(trim(p_lead),'') is null then
   raise exception 'invalid delivery event';
 end if;
 if p_event_type in ('bounced','unsubscribed','complained') and
   (nullif(trim(p_email),'') is null or position('@' in p_email)=0) then
   raise exception 'suppression recipient required';
 end if;
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
revoke all on function public.prospect_record_delivery_atomic(uuid,text,text,text,text,text) from public,anon,authenticated;
grant execute on function public.prospect_record_delivery_atomic(uuid,text,text,text,text,text) to service_role;

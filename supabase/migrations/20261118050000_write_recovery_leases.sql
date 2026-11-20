-- ECO-002: atomic recovery leases, scheduled retry, and fenced settlement.
ALTER TABLE public.write_invoke_idempotency
 ADD COLUMN IF NOT EXISTS recovery_lease_token uuid,
 ADD COLUMN IF NOT EXISTS recovery_lease_expires_at timestamptz,
 ADD COLUMN IF NOT EXISTS recovery_next_attempt_at timestamptz,
 ADD COLUMN IF NOT EXISTS recovery_attempts integer NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_write_recovery_ready
 ON public.write_invoke_idempotency(recovery_next_attempt_at, updated_at)
 WHERE status='uncertain';

CREATE OR REPLACE FUNCTION public.claim_due_write_recoveries(
 p_limit integer DEFAULT 25, p_lease_seconds integer DEFAULT 120
) RETURNS TABLE(org_id uuid, idempotency_key text, invoke_action text,
 connector_id text, original_args jsonb, recovery_lease_token uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
BEGIN
 IF auth.role() IS DISTINCT FROM 'service_role' THEN
   RAISE EXCEPTION 'service_role_required' USING ERRCODE='42501';
 END IF;
 UPDATE public.write_invoke_idempotency w
 SET status='uncertain', claim_token=NULL, lease_expires_at=NULL, updated_at=now()
 WHERE status='in_progress' AND (lease_expires_at IS NULL OR lease_expires_at <= now());
 RETURN QUERY
 WITH locked AS (
 SELECT w.id FROM public.write_invoke_idempotency w
 WHERE w.status='uncertain'
   AND (w.recovery_next_attempt_at IS NULL OR w.recovery_next_attempt_at <= now())
   AND (w.recovery_lease_expires_at IS NULL OR w.recovery_lease_expires_at <= now())
 ORDER BY w.updated_at, w.id
 FOR UPDATE SKIP LOCKED
 LIMIT LEAST(GREATEST(p_limit,1),100)
 ), claimed AS (
 UPDATE public.write_invoke_idempotency w
 SET recovery_lease_token=gen_random_uuid(),
     recovery_lease_expires_at=now()+make_interval(secs=>GREATEST(30,LEAST(p_lease_seconds,3600))),
     recovery_attempts=w.recovery_attempts+1,
     updated_at=now()
 FROM locked WHERE w.id=locked.id
 RETURNING w.org_id,w.idempotency_key,w.invoke_action,w.connector_id,w.original_args,w.recovery_lease_token
 ) SELECT * FROM claimed;
END;$$;

CREATE OR REPLACE FUNCTION public.settle_leased_write_recovery(
 p_org_id uuid,p_key text,p_lease_token uuid,p_status text,
 p_result jsonb DEFAULT '{}'::jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
DECLARE v_changed integer;
BEGIN
 IF auth.role() IS DISTINCT FROM 'service_role' THEN
  RETURN jsonb_build_object('outcome','rejected','reason','service_role_required');
 END IF;
 IF p_status NOT IN ('completed','failed') THEN
  RETURN jsonb_build_object('outcome','rejected','reason','invalid_status');
 END IF;
 UPDATE public.write_invoke_idempotency
 SET status=p_status,result=coalesce(p_result,'{}'::jsonb),
     recovery_lease_token=NULL,recovery_lease_expires_at=NULL,
     recovery_next_attempt_at=NULL,updated_at=now()
 WHERE org_id=p_org_id AND idempotency_key=p_key AND status='uncertain'
  AND recovery_lease_token=p_lease_token AND recovery_lease_expires_at>now();
 GET DIAGNOSTICS v_changed=ROW_COUNT;
 RETURN jsonb_build_object('outcome',CASE WHEN v_changed=1 THEN 'reconciled' ELSE 'rejected' END);
END;$$;

CREATE OR REPLACE FUNCTION public.defer_leased_write_recovery(
 p_org_id uuid,p_key text,p_lease_token uuid
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
DECLARE v_changed integer;
BEGIN
 IF auth.role() IS DISTINCT FROM 'service_role' THEN
  RETURN jsonb_build_object('outcome','rejected');
 END IF;
 UPDATE public.write_invoke_idempotency w
 SET recovery_lease_token=NULL,recovery_lease_expires_at=NULL,
     recovery_next_attempt_at=now()+make_interval(secs=>
        LEAST(86400, 60*power(2,LEAST(recovery_attempts,10)))::integer),
     updated_at=now()
 WHERE org_id=p_org_id AND idempotency_key=p_key AND status='uncertain'
  AND recovery_lease_token=p_lease_token AND recovery_lease_expires_at>now();
 GET DIAGNOSTICS v_changed=ROW_COUNT;
 RETURN jsonb_build_object('outcome',CASE WHEN v_changed=1 THEN 'deferred' ELSE 'rejected' END);
END;$$;
REVOKE ALL ON FUNCTION public.claim_due_write_recoveries(integer,integer) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.settle_leased_write_recovery(uuid,text,uuid,text,jsonb) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.defer_leased_write_recovery(uuid,text,uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.claim_due_write_recoveries(integer,integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.settle_leased_write_recovery(uuid,text,uuid,text,jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.defer_leased_write_recovery(uuid,text,uuid) TO service_role;

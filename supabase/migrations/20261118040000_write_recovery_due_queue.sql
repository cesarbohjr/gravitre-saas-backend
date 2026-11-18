-- ECO-002 durable recovery queue: expired claims become uncertain, never
-- eligible for a blind provider retry. Service-role worker polls this ledger.
CREATE INDEX IF NOT EXISTS idx_write_recovery_due
 ON public.write_invoke_idempotency (updated_at, org_id)
 WHERE status = 'uncertain';

CREATE OR REPLACE FUNCTION public.list_due_write_recoveries(
 p_limit int DEFAULT 50
) RETURNS TABLE (
 org_id uuid, idempotency_key text, invoke_action text,
 connector_id text, original_args jsonb
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public
AS $$
BEGIN
 IF auth.role() IS DISTINCT FROM 'service_role' THEN
   RAISE EXCEPTION 'service_role_required' USING ERRCODE='42501';
 END IF;
 -- Expiration is a durable state transition. Never reissue the write.
 UPDATE public.write_invoke_idempotency
 SET status='uncertain', claim_token=NULL, lease_expires_at=NULL,
     updated_at=now()
 WHERE status='in_progress' AND
       (lease_expires_at IS NULL OR lease_expires_at <= now());
 RETURN QUERY
 SELECT w.org_id, w.idempotency_key, w.invoke_action,
        w.connector_id, w.original_args
 FROM public.write_invoke_idempotency w
 WHERE w.status='uncertain'
 ORDER BY w.updated_at ASC
 LIMIT LEAST(GREATEST(p_limit,1),100);
END;
$$;
REVOKE ALL ON FUNCTION public.list_due_write_recoveries(int) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.list_due_write_recoveries(int) TO service_role;

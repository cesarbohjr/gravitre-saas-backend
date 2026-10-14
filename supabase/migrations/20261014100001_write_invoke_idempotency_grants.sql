-- Service-role-only privileges for write invoke idempotency (split from 20261014100000 for CI scan).

GRANT ALL ON TABLE public.write_invoke_idempotency TO service_role;
GRANT EXECUTE ON FUNCTION public.claim_write_invoke_idempotency(uuid, text, text, text, int) TO service_role;
GRANT EXECUTE ON FUNCTION public.finalize_write_invoke_idempotency(uuid, text, uuid, text, jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.reconcile_write_invoke_idempotency(uuid, text, text, jsonb) TO service_role;

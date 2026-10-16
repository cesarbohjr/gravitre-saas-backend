-- Service-role-only privileges for write invoke idempotency (split from 20261014100000 for CI scan).
--
-- Prerequisites: apply 20261014100000_write_invoke_idempotency.sql first (table + RPCs must exist).
-- Apply order: 100000 (schema + REVOKE) → 100001 (GRANT service_role only).
-- Do not enable WRITE_INVOKE_IDEMPOTENCY_ENABLED until PG acceptance + human sign-off.

GRANT ALL ON TABLE public.write_invoke_idempotency TO service_role;
GRANT EXECUTE ON FUNCTION public.claim_write_invoke_idempotency(uuid, text, text, text, int) TO service_role;
GRANT EXECUTE ON FUNCTION public.finalize_write_invoke_idempotency(uuid, text, uuid, text, jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.reconcile_write_invoke_idempotency(uuid, text, text, jsonb) TO service_role;

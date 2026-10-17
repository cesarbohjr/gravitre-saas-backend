-- Atomic audit: trigger failure rolls back the grant mutation.
-- Does not add parent organization access or customer-data policies.
BEGIN;
CREATE OR REPLACE FUNCTION public.msp_delegation_audit_mutation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO public.msp_delegation_audit
      (delegation_id, provider_org_id, customer_org_id, actor_user_id, action)
    VALUES
      (NEW.id, NEW.provider_org_id, NEW.customer_org_id,
       NEW.approved_by_customer_user_id, 'grant.created');
  ELSIF TG_OP = 'UPDATE' AND OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL THEN
    -- Revoking actor must be supplied by the authenticated service in session context.
    -- Until a trusted actor context is wired, do not permit unauditable revocations.
    IF NULLIF(current_setting('app.msp_actor_user_id', true), '') IS NULL THEN
      RAISE EXCEPTION 'Missing trusted MSP revocation actor';
    END IF;
    INSERT INTO public.msp_delegation_audit
      (delegation_id, provider_org_id, customer_org_id, actor_user_id, action)
    VALUES
      (NEW.id, NEW.provider_org_id, NEW.customer_org_id,
       current_setting('app.msp_actor_user_id')::uuid, 'grant.revoked');
  END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.msp_delegation_audit_mutation() FROM PUBLIC, anon, authenticated;
DROP TRIGGER IF EXISTS trg_msp_delegation_audit ON public.msp_delegations;
CREATE TRIGGER trg_msp_delegation_audit
AFTER INSERT OR UPDATE OF revoked_at ON public.msp_delegations
FOR EACH ROW EXECUTE FUNCTION public.msp_delegation_audit_mutation();
COMMIT;

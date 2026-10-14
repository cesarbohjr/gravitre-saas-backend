-- Release 2: durable write invoke idempotency (retry-safe connector writes).
--
-- Preflight:
--   SELECT to_regclass('public.write_invoke_idempotency');
--
-- Rollback:
--   DROP TABLE IF EXISTS public.write_invoke_idempotency;

CREATE TABLE IF NOT EXISTS public.write_invoke_idempotency (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  idempotency_key text NOT NULL,
  invoke_action text NOT NULL,
  logical_action_id text,
  status text NOT NULL DEFAULT 'completed' CHECK (status IN ('completed', 'failed')),
  result jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_write_invoke_idempotency_org_created
  ON public.write_invoke_idempotency (org_id, created_at DESC);

ALTER TABLE public.write_invoke_idempotency ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS write_invoke_idempotency_org ON public.write_invoke_idempotency;
CREATE POLICY write_invoke_idempotency_org ON public.write_invoke_idempotency
  FOR ALL
  USING (public.auth_org_accessible(org_id))
  WITH CHECK (public.auth_org_accessible(org_id));

COMMENT ON TABLE public.write_invoke_idempotency IS
  'Completed connector write results keyed for safe retries (Release 2).';

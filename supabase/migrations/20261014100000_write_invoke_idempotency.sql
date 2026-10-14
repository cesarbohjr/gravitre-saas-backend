-- Release 2: write invoke idempotency ledger (service-role mutations only).
--
-- Preflight:
--   SELECT to_regclass('public.write_invoke_idempotency');
--
-- Rollback:
--   DROP FUNCTION IF EXISTS public.claim_write_invoke_idempotency(uuid, text, text, text, int);
--   DROP TABLE IF EXISTS public.write_invoke_idempotency;

CREATE TABLE IF NOT EXISTS public.write_invoke_idempotency (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  idempotency_key text NOT NULL,
  invoke_action text NOT NULL,
  logical_action_id text,
  status text NOT NULL DEFAULT 'in_progress'
    CHECK (status IN ('in_progress', 'completed', 'failed', 'uncertain')),
  result jsonb NOT NULL DEFAULT '{}'::jsonb,
  claimed_at timestamptz NOT NULL DEFAULT now(),
  lease_expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_write_invoke_idempotency_org_created
  ON public.write_invoke_idempotency (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_write_invoke_idempotency_lease
  ON public.write_invoke_idempotency (lease_expires_at)
  WHERE status = 'in_progress';

ALTER TABLE public.write_invoke_idempotency ENABLE ROW LEVEL SECURITY;

-- No member/authenticated policies: backend service role only.
REVOKE ALL ON TABLE public.write_invoke_idempotency FROM PUBLIC;
REVOKE ALL ON TABLE public.write_invoke_idempotency FROM anon;
REVOKE ALL ON TABLE public.write_invoke_idempotency FROM authenticated;

COMMENT ON TABLE public.write_invoke_idempotency IS
  'Backend-only ledger for write invoke claims and completed replays (Release 2).';

CREATE OR REPLACE FUNCTION public.claim_write_invoke_idempotency(
  p_org_id uuid,
  p_key text,
  p_invoke_action text,
  p_logical_action_id text,
  p_lease_seconds int DEFAULT 300
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_now timestamptz := now();
  v_lease timestamptz := v_now + make_interval(secs => GREATEST(p_lease_seconds, 30));
  v_row public.write_invoke_idempotency%ROWTYPE;
BEGIN
  INSERT INTO public.write_invoke_idempotency (
    org_id, idempotency_key, invoke_action, logical_action_id, status, lease_expires_at
  ) VALUES (
    p_org_id, p_key, p_invoke_action, p_logical_action_id, 'in_progress', v_lease
  )
  ON CONFLICT (org_id, idempotency_key) DO NOTHING
  RETURNING * INTO v_row;

  IF FOUND THEN
    RETURN jsonb_build_object('outcome', 'claimed', 'status', 'in_progress');
  END IF;

  SELECT * INTO v_row
  FROM public.write_invoke_idempotency
  WHERE org_id = p_org_id AND idempotency_key = p_key
  FOR UPDATE;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('outcome', 'error', 'reason', 'missing_after_conflict');
  END IF;

  IF v_row.status = 'completed' THEN
    RETURN jsonb_build_object(
      'outcome', 'replay',
      'status', 'completed',
      'result', v_row.result
    );
  END IF;

  IF v_row.status = 'uncertain' THEN
    RETURN jsonb_build_object('outcome', 'blocked', 'status', 'uncertain');
  END IF;

  IF v_row.status = 'in_progress' AND v_row.lease_expires_at IS NOT NULL AND v_row.lease_expires_at > v_now THEN
    RETURN jsonb_build_object('outcome', 'blocked', 'status', 'in_progress');
  END IF;

  IF v_row.status IN ('in_progress', 'failed') THEN
    UPDATE public.write_invoke_idempotency
    SET status = 'in_progress',
        invoke_action = p_invoke_action,
        logical_action_id = p_logical_action_id,
        lease_expires_at = v_lease,
        updated_at = v_now
    WHERE id = v_row.id;
    RETURN jsonb_build_object('outcome', 'claimed', 'status', 'in_progress');
  END IF;

  RETURN jsonb_build_object('outcome', 'blocked', 'status', v_row.status);
END;
$$;

REVOKE ALL ON FUNCTION public.claim_write_invoke_idempotency(uuid, text, text, text, int) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.claim_write_invoke_idempotency(uuid, text, text, text, int) FROM anon;
REVOKE ALL ON FUNCTION public.claim_write_invoke_idempotency(uuid, text, text, text, int) FROM authenticated;

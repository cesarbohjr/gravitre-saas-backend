-- BE-21 governed recommendations. Backend service-role access only.
-- No direct client INSERT/UPDATE/DELETE: approval authority belongs to the API.
CREATE TABLE IF NOT EXISTS public.operator_recommendations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
 operator_type text NOT NULL CHECK (operator_type = 'workflow-param-suggester'),
 recommendation jsonb NOT NULL,
 status text NOT NULL DEFAULT 'pending'
   CHECK (status IN ('pending','claimed','rejected','running','pending_approval','verification_inconclusive')),
 created_by uuid NOT NULL REFERENCES auth.users(id),
 confirmed_by uuid REFERENCES auth.users(id),
 run_id text,
 expires_at timestamptz NOT NULL DEFAULT (now() + interval '24 hours'),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_operator_recommendations_org_state
 ON public.operator_recommendations(org_id, status, expires_at);
ALTER TABLE public.operator_recommendations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.operator_recommendations FROM PUBLIC, anon, authenticated;
-- No member policies or auth.role checks. Backend service-role bypasses RLS.
-- The API checks org ownership and canonical workflow permission at execution.

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.operator_recommendations TO service_role;

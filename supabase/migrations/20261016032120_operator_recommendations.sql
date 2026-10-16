-- BE-21: operator_recommendations table + RLS
--
-- Purpose: stores operator-suggested writes awaiting user confirmation.
-- Operator types (e.g. draft-assistant, workflow-param-suggester) create rows;
-- users confirm via POST /api/operators/:type/confirm; the row is updated and
-- the confirmed action executed.
--
-- Preflight (read-only):
--   SELECT table_name FROM information_schema.tables
--    WHERE table_schema = 'public' AND table_name = 'operator_recommendations';
--
-- Rollback:
--   DROP TABLE IF EXISTS public.operator_recommendations;

CREATE TABLE IF NOT EXISTS public.operator_recommendations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    operator_type   text NOT NULL CHECK (char_length(operator_type) <= 80),
    context         jsonb NOT NULL DEFAULT '{}'::jsonb,
    recommendation  jsonb NOT NULL DEFAULT '{}'::jsonb,
    status          text NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'confirmed', 'rejected', 'expired', 'executed')),
    confirmed_by    uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    executed_at     timestamptz,
    result          jsonb,
    expires_at      timestamptz NOT NULL DEFAULT (now() + interval '24 hours'),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- Index for frequent per-org lookups
CREATE INDEX IF NOT EXISTS idx_operator_recommendations_org_id
    ON public.operator_recommendations (org_id, status, created_at DESC);

-- Index for type + org lookup used by the confirm endpoint
CREATE INDEX IF NOT EXISTS idx_operator_recommendations_type
    ON public.operator_recommendations (org_id, operator_type, status);

COMMENT ON TABLE public.operator_recommendations IS
    'BE-21: operator-suggested write actions awaiting user confirmation.';

-- RLS
ALTER TABLE public.operator_recommendations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_members_select_recommendations"
    ON public.operator_recommendations FOR SELECT
    USING (
        org_id IN (
            SELECT org_id FROM public.org_members WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "org_members_insert_recommendations"
    ON public.operator_recommendations FOR INSERT
    WITH CHECK (
        org_id IN (
            SELECT org_id FROM public.org_members WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "org_members_update_recommendations"
    ON public.operator_recommendations FOR UPDATE
    USING (
        org_id IN (
            SELECT org_id FROM public.org_members WHERE user_id = auth.uid()
        )
    );

-- Service-role bypass (backend service client)
CREATE POLICY "service_role_all_recommendations"
    ON public.operator_recommendations FOR ALL
    USING (auth.role() = 'service_role');

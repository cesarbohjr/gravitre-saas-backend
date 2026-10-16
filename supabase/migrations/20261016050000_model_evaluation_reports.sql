-- Intelligence Track: model evaluation report storage.
--
-- Stores offline LLM quality evaluation reports produced by
-- llm_workflow_evaluation.evaluate_models. Reports are immutable once written;
-- approval (routing_approved) is the only mutable column, updated by the
-- /api/admin/model-evaluation/{id}/approve endpoint.
--
-- Rollback: DROP TABLE IF EXISTS public.model_evaluation_reports;

CREATE TABLE IF NOT EXISTS public.model_evaluation_reports (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          uuid        NOT NULL,
    run_by          uuid        NOT NULL,          -- auth.uid() of the admin who triggered the run
    models          text[]      NOT NULL,           -- catalog model ids evaluated
    dataset_sha256  text        NOT NULL,           -- SHA-256 of the evaluation case set
    catalog_sha256  text        NOT NULL,           -- SHA-256 of catalog snapshot at run time
    scope           text        NOT NULL DEFAULT 'synthetic_structured_planning_only',
    report          jsonb       NOT NULL,           -- full evaluate_models() return value
    routing_approved boolean    NOT NULL DEFAULT false,
    approved_by     uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
    approved_at     timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Read recent reports by org (most common admin query)
CREATE INDEX IF NOT EXISTS idx_model_eval_reports_org_created
    ON public.model_evaluation_reports (org_id, created_at DESC);

-- Quickly find unapproved reports for a given dataset
CREATE INDEX IF NOT EXISTS idx_model_eval_reports_dataset
    ON public.model_evaluation_reports (dataset_sha256, routing_approved)
    WHERE routing_approved = false;

-- RLS: platform service role can do everything; authenticated admins may
-- read reports for orgs they administer.
ALTER TABLE public.model_evaluation_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY model_eval_reports_service_all
    ON public.model_evaluation_reports
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Authenticated users may read their own org's reports when they are an org admin.
CREATE POLICY model_eval_reports_admin_read
    ON public.model_evaluation_reports
    FOR SELECT
    TO authenticated
    USING (
        org_id IN (
            SELECT om.org_id
            FROM public.organization_members om
            WHERE om.user_id = auth.uid()
              AND om.role IN ('admin', 'owner')
        )
    );

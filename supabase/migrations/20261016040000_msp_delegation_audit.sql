-- Release 4: MSP delegation audit log.
--
-- Records every successful parent-org → child-org delegation event so security
-- teams can review cross-org access patterns. This is an append-only audit table;
-- no application logic deletes from it. Separate from the main audit_log to keep
-- MSP-specific queries fast (org-scoped RLS on audit_log is broader).
--
-- Rollback:
--   DROP TABLE IF EXISTS public.msp_delegation_events CASCADE;

CREATE TABLE IF NOT EXISTS public.msp_delegation_events (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid        NOT NULL,
    parent_org_id   uuid        NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    client_org_id   uuid        NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    event_type      text        NOT NULL CHECK (char_length(event_type) <= 80),
    -- 'access_granted'  — msp_parent_grants_access returned True (org context resolved)
    -- 'client_switched' — POST /api/msp/switch-client issued a scoped token
    -- 'client_listed'   — GET /api/msp/client-orgs called
    metadata        jsonb       NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Query pattern: "show all delegation events for org X in last 30 days"
CREATE INDEX IF NOT EXISTS idx_msp_delegation_events_client_org
    ON public.msp_delegation_events (client_org_id, created_at DESC);

-- Query pattern: "show all clients an MSP user has accessed"
CREATE INDEX IF NOT EXISTS idx_msp_delegation_events_user
    ON public.msp_delegation_events (user_id, created_at DESC);

-- Query pattern: "all events under a parent org"
CREATE INDEX IF NOT EXISTS idx_msp_delegation_events_parent_org
    ON public.msp_delegation_events (parent_org_id, created_at DESC);

-- RLS: parent-org admins can read delegation events for their child orgs;
-- service_role has full access for backend writes.
ALTER TABLE public.msp_delegation_events ENABLE ROW LEVEL SECURITY;

-- Backend (service_role) writes all rows.
CREATE POLICY msp_delegation_events_service_all
    ON public.msp_delegation_events
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Parent-org admin members can read events for their orgs.
CREATE POLICY msp_delegation_events_parent_read
    ON public.msp_delegation_events
    FOR SELECT
    TO authenticated
    USING (
        parent_org_id IN (
            SELECT org_id
            FROM public.organization_members
            WHERE user_id = auth.uid()
              AND role IN ('admin', 'owner')
        )
    );

COMMENT ON TABLE public.msp_delegation_events IS
    'Append-only audit log of MSP parent→child org delegation access events (Release 4).';

-- External Distribution: org-scoped API key table for third-party / integration access.
--
-- Keys are issued via POST /api/org/{org_id}/api-keys and validated in
-- app/auth/api_key_middleware.py. The stored value is an SHA-256 hash of the
-- raw key; the raw key (prefix grav_live_ or grav_test_) is only ever shown
-- once at creation time.
--
-- Rollback: DROP TABLE IF EXISTS public.org_api_keys;

CREATE TABLE IF NOT EXISTS public.org_api_keys (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          uuid        NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    created_by      uuid        NOT NULL,              -- auth.uid() of the admin who created it
    label           text        NOT NULL CHECK (char_length(label) >= 1 AND char_length(label) <= 120),
    key_prefix      text        NOT NULL,              -- first 12 chars of the raw key (safe to display)
    key_hash        text        NOT NULL UNIQUE,       -- SHA-256(raw_key) hex — never the key itself
    scopes          text[]      NOT NULL DEFAULT '{}', -- e.g. {"chat:read","chat:write"}
    expires_at      timestamptz,                       -- NULL = never expires
    last_used_at    timestamptz,
    revoked_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Look up a key during validation (by hash)
CREATE UNIQUE INDEX IF NOT EXISTS idx_org_api_keys_hash
    ON public.org_api_keys (key_hash)
    WHERE revoked_at IS NULL;

-- List active keys for an org
CREATE INDEX IF NOT EXISTS idx_org_api_keys_org_active
    ON public.org_api_keys (org_id, created_at DESC)
    WHERE revoked_at IS NULL;

-- RLS: service_role full access; org admins can manage their own org's keys;
-- authenticated users can read keys they created.
ALTER TABLE public.org_api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY org_api_keys_service_all
    ON public.org_api_keys
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Org admins can read/insert/update keys for their org.
CREATE POLICY org_api_keys_admin_rw
    ON public.org_api_keys
    FOR ALL
    TO authenticated
    USING (
        org_id IN (
            SELECT om.org_id
            FROM public.organization_members om
            WHERE om.user_id = auth.uid()
              AND om.role IN ('admin', 'owner')
        )
    )
    WITH CHECK (
        org_id IN (
            SELECT om.org_id
            FROM public.organization_members om
            WHERE om.user_id = auth.uid()
              AND om.role IN ('admin', 'owner')
        )
    );

COMMENT ON TABLE public.org_api_keys IS
  'Org-scoped API keys for external/integration access (External Distribution, Release 7). '
  'key_hash holds SHA-256 of the raw key; the raw key is never stored.';

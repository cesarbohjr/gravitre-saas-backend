-- Part 8 of the storage migration (see 20261020081535_storage_retention_metering.sql).

-- -----------------------------------------------------------------------------
-- 6) Bring-your-own storage target
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.org_storage_targets (
  org_id uuid PRIMARY KEY REFERENCES public.organizations(id) ON DELETE CASCADE,
  provider text NOT NULL DEFAULT 's3' CHECK (provider IN ('s3')),
  endpoint_url text,
  region text NOT NULL,
  bucket text NOT NULL,
  path_prefix text NOT NULL DEFAULT '',
  access_key_id_enc text NOT NULL,
  secret_access_key_enc text NOT NULL,
  access_key_hint text,
  status text NOT NULL DEFAULT 'untested' CHECK (status IN ('untested', 'verified', 'failed')),
  last_tested_at timestamptz,
  last_test_error text,
  created_by uuid,
  updated_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.org_storage_targets IS
  'Org-owned S3-compatible bucket for uploaded files only. Credentials encrypted by the backend; never readable by clients.';

ALTER TABLE public.org_storage_targets ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.org_storage_targets FROM anon, authenticated;
GRANT ALL ON public.org_storage_targets TO service_role;

-- -----------------------------------------------------------------------------
-- 7) Where each uploaded file lives
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.org_file_objects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  location text NOT NULL CHECK (location IN ('supabase', 'byo')),
  bucket text NOT NULL,
  object_key text NOT NULL,
  logical_bucket text NOT NULL,
  logical_path text NOT NULL,
  byte_size bigint NOT NULL DEFAULT 0 CHECK (byte_size >= 0),
  content_type text,
  purpose text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT org_file_objects_logical_once UNIQUE (org_id, logical_bucket, logical_path)
);

CREATE INDEX IF NOT EXISTS idx_org_file_objects_org_created
  ON public.org_file_objects (org_id, created_at DESC);

ALTER TABLE public.org_file_objects ENABLE ROW LEVEL SECURITY;

-- Prod ran this part without the DROP (the table was new, so the end state is the
-- same); the DROP keeps the file re-runnable.
DROP POLICY IF EXISTS org_file_objects_read ON public.org_file_objects;
CREATE POLICY org_file_objects_read ON public.org_file_objects FOR SELECT
  USING (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()));

-- Members read their own org's rows; only the service role writes.
REVOKE ALL ON public.org_file_objects FROM anon, authenticated;
GRANT SELECT ON public.org_file_objects TO authenticated;
GRANT ALL ON public.org_file_objects TO service_role;

-- -----------------------------------------------------------------------------
-- 8) Private archive bucket
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF to_regclass('storage.buckets') IS NOT NULL THEN
    INSERT INTO storage.buckets (id, name, public)
    VALUES ('audit-archive', 'audit-archive', false)
    ON CONFLICT (id) DO NOTHING;
  END IF;
END
$$;

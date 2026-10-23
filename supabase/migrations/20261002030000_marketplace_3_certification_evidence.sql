-- Gravitre Marketplace 3.0 certification evidence.
-- Certification is bound to the exact Outcome Pack config digest so changing a
-- package invalidates previous proof until the new version is re-certified.

CREATE TABLE IF NOT EXISTS public.marketplace_outcome_pack_certifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  asset_id uuid NOT NULL REFERENCES public.marketplace_assets(id) ON DELETE CASCADE,
  config_digest text NOT NULL,
  config_snapshot jsonb NOT NULL,
  environment text NOT NULL DEFAULT 'production' CHECK (environment = 'production'),
  certification_level text NOT NULL
    CHECK (certification_level IN (
      'compatible',
      'tested',
      'governed',
      'production_verified',
      'outcome_verified'
    )),
  publish_ready boolean NOT NULL DEFAULT false,
  report jsonb NOT NULL DEFAULT '{}'::jsonb,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  certified_by uuid,
  certified_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL DEFAULT (now() + interval '30 days'),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (asset_id, config_digest)
);

CREATE INDEX IF NOT EXISTS idx_marketplace_outcome_pack_cert_org
  ON public.marketplace_outcome_pack_certifications (org_id, certified_at DESC);

CREATE INDEX IF NOT EXISTS idx_marketplace_outcome_pack_cert_asset
  ON public.marketplace_outcome_pack_certifications (asset_id, certified_at DESC);

ALTER TABLE public.marketplace_outcome_pack_certifications ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS marketplace_outcome_pack_certifications_org_scope
  ON public.marketplace_outcome_pack_certifications;

-- Evidence is authoritative server state. Membership grants visibility, never
-- permission to forge or delete production certification.
REVOKE ALL ON public.marketplace_outcome_pack_certifications FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.marketplace_outcome_pack_certifications TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.marketplace_outcome_pack_certifications TO service_role;
CREATE POLICY marketplace_outcome_pack_certifications_org_scope
  ON public.marketplace_outcome_pack_certifications FOR SELECT TO authenticated
  USING (org_id IN (SELECT om.org_id FROM public.organization_members om
                   WHERE om.user_id = (SELECT auth.uid())));

-- Independently executed scenario checks are written only by the trusted
-- acceptance runner, never from a publish request or editable asset metadata.
CREATE TABLE IF NOT EXISTS public.marketplace_outcome_pack_checks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  asset_id uuid NOT NULL REFERENCES public.marketplace_assets(id) ON DELETE CASCADE,
  config_digest text NOT NULL,
  check_kind text NOT NULL CHECK (check_kind IN (
    'fresh_install_passed','golden_path_passed','failure_path_passed',
    'permissions_passed','kpi_reconciliation_passed','source_of_record_verification_passed')),
  environment text NOT NULL CHECK (environment = 'production'),
  passed boolean NOT NULL DEFAULT false,
  evidence_ref text NOT NULL CHECK (length(btrim(evidence_ref)) > 0),
  checked_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_outcome_pack_checks_current
  ON public.marketplace_outcome_pack_checks (org_id, asset_id, config_digest, checked_at DESC);
ALTER TABLE public.marketplace_outcome_pack_checks ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.marketplace_outcome_pack_checks FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON public.marketplace_outcome_pack_checks TO service_role;

-- The final publish check runs in the database transaction, so an API preflight
-- cannot race a config edit or be bypassed by a catalog seed/direct table write.
-- JSONB equality binds the exact persisted configuration, including all fields;
-- Python's digest remains the lookup key, not a second SQL serialization scheme.
CREATE OR REPLACE FUNCTION public.enforce_outcome_pack_publication()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
BEGIN
  IF NEW.asset_type = 'outcome_pack' AND NEW.status = 'published' THEN
    IF current_user IN ('anon', 'authenticated') THEN
      RAISE EXCEPTION 'Outcome Pack publication requires the governed server path' USING ERRCODE = '42501';
    END IF;
    PERFORM 1 FROM public.marketplace_outcome_pack_certifications c
      WHERE c.asset_id = NEW.id AND c.org_id = NEW.org_id
        AND c.config_snapshot = NEW.config AND c.environment = 'production'
        AND c.certified_at <= now() AND c.expires_at > now()
        AND c.publish_ready IS TRUE
        AND c.certification_level IN ('production_verified', 'outcome_verified')
      FOR SHARE;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'OUTCOME_PACK_CERTIFICATION_REQUIRED' USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.enforce_outcome_pack_publication() FROM PUBLIC, anon, authenticated;
DROP TRIGGER IF EXISTS outcome_pack_publication_evidence ON public.marketplace_assets;
CREATE TRIGGER outcome_pack_publication_evidence
  BEFORE INSERT OR UPDATE ON public.marketplace_assets
  FOR EACH ROW EXECUTE FUNCTION public.enforce_outcome_pack_publication();

COMMENT ON TABLE public.marketplace_outcome_pack_certifications IS
  'Marketplace 3.0 certification evidence bound to an immutable Outcome Pack config digest.';

-- Wave 2: extend knowledge_sources with licensing/retrieval/freshness granularity.
-- Still one A–E system — no parallel schema.

ALTER TABLE public.knowledge_sources
  ADD COLUMN IF NOT EXISTS licence_verified boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS license_verified_at timestamptz,
  ADD COLUMN IF NOT EXISTS retrieval_semantic boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS retrieval_keyword boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS citation_required boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS refresh_days integer,
  ADD COLUMN IF NOT EXISTS effective_date_sensitive boolean NOT NULL DEFAULT false;

-- Backfill: prior live-verified / filtered sources already in corpus
UPDATE public.knowledge_sources
SET
  licence_verified = true,
  license_verified_at = coalesce(license_verified_at, last_refreshed_at, updated_at, now())
WHERE legal_review_status IN ('verified_live', 'filtered_provenance')
  AND commercial_use_allowed = true
  AND status = 'active';

-- Hard DB gate: active A/B corpus rows must be licence-verified (OpenStax lesson).
ALTER TABLE public.knowledge_sources
  DROP CONSTRAINT IF EXISTS knowledge_sources_licence_verified_for_ingest;

ALTER TABLE public.knowledge_sources
  ADD CONSTRAINT knowledge_sources_licence_verified_for_ingest
  CHECK (
    status <> 'active'
    OR license_type NOT IN ('A', 'B')
    OR licence_verified = true
  );

COMMENT ON COLUMN public.knowledge_sources.licence_verified IS
  'True only after live license terms confirmed at ingest time; hard gate for shared corpus.';
COMMENT ON COLUMN public.knowledge_sources.license_verified_at IS
  'Timestamp of last live license verification.';
COMMENT ON COLUMN public.knowledge_sources.refresh_days IS
  'Expected refresh cadence in days (null = use refresh_frequency enum only).';
COMMENT ON COLUMN public.knowledge_sources.effective_date_sensitive IS
  'True when superseded/effective dates matter for retrieval ranking.';

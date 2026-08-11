-- Extend knowledge_sources with license granularity fields (A–E remains canonical).
-- Maps proposed ingestion_policy concepts onto existing columns + these metadata fields
-- (FULL/FILTERED/API/REFRESHABLE/LIVE_RETRIEVAL/METADATA_ONLY/BLOCKED → license_type +
--  ingestion_method + commercial_use_allowed + legal_review_status — not a parallel schema).

ALTER TABLE public.knowledge_sources
  ADD COLUMN IF NOT EXISTS license text,
  ADD COLUMN IF NOT EXISTS license_url text,
  ADD COLUMN IF NOT EXISTS derivatives_allowed boolean,
  ADD COLUMN IF NOT EXISTS third_party_content_present boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS legal_review_status text NOT NULL DEFAULT 'unreviewed';

ALTER TABLE public.knowledge_sources
  DROP CONSTRAINT IF EXISTS knowledge_sources_legal_review_status_check;

ALTER TABLE public.knowledge_sources
  ADD CONSTRAINT knowledge_sources_legal_review_status_check
  CHECK (legal_review_status IN (
    'unreviewed',
    'verified_live',
    'filtered_provenance',
    'blocked_nc',
    'blocked_unconfirmed',
    'live_retrieval_only',
    'pending_credentials'
  ));

-- Hard DB gate: type A/B permanent corpus rows must affirm commercial use.
-- Held / paused / D / C / E rows may keep commercial_use_allowed=false.
ALTER TABLE public.knowledge_sources
  DROP CONSTRAINT IF EXISTS knowledge_sources_commercial_use_for_ingest;

ALTER TABLE public.knowledge_sources
  ADD CONSTRAINT knowledge_sources_commercial_use_for_ingest
  CHECK (
    status <> 'active'
    OR license_type NOT IN ('A', 'B')
    OR commercial_use_allowed = true
  );

COMMENT ON COLUMN public.knowledge_sources.license IS
  'SPDX-ish or human license label (e.g. CC-BY-4.0, US-Gov-Work); A–E remains license_type.';
COMMENT ON COLUMN public.knowledge_sources.license_url IS
  'Canonical page where license terms were live-verified.';
COMMENT ON COLUMN public.knowledge_sources.derivatives_allowed IS
  'Whether derivatives are permitted under verified terms; null=unconfirmed.';
COMMENT ON COLUMN public.knowledge_sources.third_party_content_present IS
  'True when source may embed third-party licensed material (requires provenance filter).';
COMMENT ON COLUMN public.knowledge_sources.legal_review_status IS
  'Live-verification / gate status; complements license_type A–E (does not replace it).';

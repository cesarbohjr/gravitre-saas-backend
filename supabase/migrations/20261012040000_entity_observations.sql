-- Phase 3: customer/account observations and behavioural signals.
--
-- Two separate stores, on purpose:
--   * entity_observations: what a customer said, as judged by a versioned extractor
--     (sentiment, urgency, churn-risk language, expansion interest, support friction).
--     Every row quotes its evidence and names the source record. Opt-in per org and
--     vendor (sourceDataGovernance.customerContext); customer and account scope only.
--   * entity_behavior_signals: what a customer did, computed by SQL rules from counts
--     and timestamps only (never from model judgements).
-- Both hang off org_business_entities, so deleting an entity (or a source purge that
-- removes it) deletes its observations and signals.
--
-- Preflight (read-only):
--   SELECT to_regclass('public.entity_observations'), to_regclass('public.entity_behavior_signals');
--                                                                      -- expect NULL, NULL
--   SELECT to_regclass('public.org_business_entities');               -- expect not NULL
--
-- Rollback:
--   DROP FUNCTION IF EXISTS public.compute_entity_behavior_signals(uuid, timestamptz);
--   DROP TABLE IF EXISTS public.entity_behavior_signals;
--   DROP TABLE IF EXISTS public.entity_observations;

CREATE TABLE IF NOT EXISTS public.entity_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  entity_id uuid NOT NULL REFERENCES public.org_business_entities(id) ON DELETE CASCADE,
  dimension text NOT NULL CHECK (dimension IN
    ('sentiment', 'urgency', 'churn_risk_language', 'expansion_interest', 'support_friction')),
  label text NOT NULL,
  score real NOT NULL CHECK (score BETWEEN -1 AND 1),
  confidence real NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  evidence_quote text NOT NULL CHECK (char_length(evidence_quote) BETWEEN 1 AND 400),
  source_system text NOT NULL,
  source_record_type text NOT NULL,
  source_record_id text NOT NULL,
  observed_at timestamptz NOT NULL,
  extractor_version text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'corrected', 'retracted')),
  correction jsonb,
  corrected_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  corrected_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT entity_observations_once UNIQUE
    (org_id, entity_id, dimension, source_system, source_record_id, extractor_version)
);

CREATE INDEX IF NOT EXISTS idx_entity_observations_entity_time
  ON public.entity_observations (org_id, entity_id, dimension, observed_at DESC);

CREATE TABLE IF NOT EXISTS public.entity_behavior_signals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  entity_id uuid NOT NULL REFERENCES public.org_business_entities(id) ON DELETE CASCADE,
  signal text NOT NULL CHECK (signal IN ('contact_volume_change', 'contact_gap_days')),
  value real NOT NULL,
  baseline real,
  window_end date NOT NULL,
  rule_version text NOT NULL,
  evidence_count integer NOT NULL,
  computed_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT entity_behavior_signals_once UNIQUE (org_id, entity_id, signal, window_end, rule_version)
);

CREATE INDEX IF NOT EXISTS idx_entity_behavior_signals_entity
  ON public.entity_behavior_signals (org_id, entity_id, window_end DESC);

ALTER TABLE public.entity_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.entity_behavior_signals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS entity_observations_read ON public.entity_observations;
CREATE POLICY entity_observations_read ON public.entity_observations FOR SELECT
  USING (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()));
DROP POLICY IF EXISTS entity_behavior_signals_read ON public.entity_behavior_signals;
CREATE POLICY entity_behavior_signals_read ON public.entity_behavior_signals FOR SELECT
  USING (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()));

REVOKE INSERT, UPDATE, DELETE ON public.entity_observations, public.entity_behavior_signals
  FROM anon, authenticated;
GRANT SELECT ON public.entity_observations, public.entity_behavior_signals TO authenticated;
GRANT ALL ON public.entity_observations, public.entity_behavior_signals TO service_role;

-- Behavioural rules, version 'beh-v1'. Inputs are distinct customer communications
-- (one per source record) per entity, taken from entity_observations timestamps only.
--   contact_volume_change: communications in the last 14 days divided by the average
--     per 14 days over the 56 days before that; written only when that prior window
--     holds at least 4 communications (otherwise there is no baseline to compare to).
--   contact_gap_days: days since the latest communication; written only for entities
--     with at least 3 communications in the last 90 days.
CREATE OR REPLACE FUNCTION public.compute_entity_behavior_signals(
  p_org_id uuid,
  p_as_of timestamptz DEFAULT now()
) RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_written integer := 0;
  v_n integer;
  v_day date := (p_as_of AT TIME ZONE 'UTC')::date;
BEGIN
  WITH comms AS (
    SELECT DISTINCT entity_id, source_system, source_record_id, observed_at
      FROM public.entity_observations
     WHERE org_id = p_org_id AND status <> 'retracted'
       AND observed_at <= p_as_of AND observed_at > p_as_of - interval '90 days'
  ), per_entity AS (
    SELECT entity_id,
           count(*) FILTER (WHERE observed_at > p_as_of - interval '14 days') AS recent,
           count(*) FILTER (WHERE observed_at <= p_as_of - interval '14 days'
                              AND observed_at > p_as_of - interval '70 days') AS prior
      FROM comms GROUP BY entity_id
  )
  INSERT INTO public.entity_behavior_signals
    (org_id, entity_id, signal, value, baseline, window_end, rule_version, evidence_count)
  SELECT p_org_id, entity_id, 'contact_volume_change',
         recent / (prior / 4.0), prior / 4.0, v_day, 'beh-v1', recent + prior
    FROM per_entity WHERE prior >= 4
  ON CONFLICT ON CONSTRAINT entity_behavior_signals_once
    DO UPDATE SET value = EXCLUDED.value, baseline = EXCLUDED.baseline,
                  evidence_count = EXCLUDED.evidence_count, computed_at = now();
  GET DIAGNOSTICS v_n = ROW_COUNT;
  v_written := v_written + v_n;

  WITH comms AS (
    SELECT DISTINCT entity_id, source_system, source_record_id, observed_at
      FROM public.entity_observations
     WHERE org_id = p_org_id AND status <> 'retracted'
       AND observed_at <= p_as_of AND observed_at > p_as_of - interval '90 days'
  ), per_entity AS (
    SELECT entity_id, count(*) AS n, max(observed_at) AS latest FROM comms GROUP BY entity_id
  )
  INSERT INTO public.entity_behavior_signals
    (org_id, entity_id, signal, value, baseline, window_end, rule_version, evidence_count)
  SELECT p_org_id, entity_id, 'contact_gap_days',
         extract(epoch FROM (p_as_of - latest)) / 86400.0, NULL, v_day, 'beh-v1', n
    FROM per_entity WHERE n >= 3
  ON CONFLICT ON CONSTRAINT entity_behavior_signals_once
    DO UPDATE SET value = EXCLUDED.value, evidence_count = EXCLUDED.evidence_count, computed_at = now();
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RETURN v_written + v_n;
END;
$$;

REVOKE ALL ON FUNCTION public.compute_entity_behavior_signals(uuid, timestamptz) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.compute_entity_behavior_signals(uuid, timestamptz) TO service_role;

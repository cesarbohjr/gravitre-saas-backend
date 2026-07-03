-- Phase A: unified learning signals + strategy performance ledger

CREATE TABLE IF NOT EXISTS public.intelligence_learning_signals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  signal_type text NOT NULL,
  polarity text NOT NULL CHECK (polarity IN ('positive', 'negative', 'neutral')),
  weight double precision NOT NULL DEFAULT 1.0,
  department text,
  surface text,
  strategy_key text,
  entity_type text,
  entity_id text,
  confidence_delta double precision,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_intelligence_learning_signals_org_created
  ON public.intelligence_learning_signals (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_intelligence_learning_signals_org_strategy
  ON public.intelligence_learning_signals (org_id, strategy_key, created_at DESC);

CREATE TABLE IF NOT EXISTS public.strategy_performance_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  strategy_key text NOT NULL,
  strategy_family text NOT NULL DEFAULT 'route',
  segment_key text NOT NULL DEFAULT 'default',
  outcome_polarity text NOT NULL CHECK (outcome_polarity IN ('win', 'loss', 'neutral')),
  latency_ms integer,
  approval_required boolean,
  approval_granted boolean,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_performance_org_key
  ON public.strategy_performance_records (org_id, strategy_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_strategy_performance_org_segment
  ON public.strategy_performance_records (org_id, segment_key, created_at DESC);

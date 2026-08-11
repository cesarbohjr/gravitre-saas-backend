-- Voice agent: per-agent voice_profile, org custom voices, voice_minutes metering.

-- 1) Agent voice profile (preset library id or custom_voice_v3 + TTS model + personality)
ALTER TABLE public.agents
  ADD COLUMN IF NOT EXISTS voice_profile jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN public.agents.voice_profile IS
  'Voice assignment: voice_source (preset_library|custom_voice_v3), voice_id, tts_model, personality_attributes, turn_sensitivity, language';

-- Name remains required at application layer; ensure non-null for new rows.
ALTER TABLE public.agents
  ALTER COLUMN name SET DEFAULT '';

-- 2) Org-scoped custom voices (reusable across agents)
CREATE TABLE IF NOT EXISTS public.agent_custom_voices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  elevenlabs_voice_id text NOT NULL,
  name text NOT NULL,
  description text,
  voice_description text,
  generated_voice_id text,
  model_id text DEFAULT 'eleven_ttv_v3',
  personality_attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, elevenlabs_voice_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_custom_voices_org
  ON public.agent_custom_voices(org_id);

-- 3) usage_records metric_type includes voice_minutes
ALTER TABLE public.usage_records
  DROP CONSTRAINT IF EXISTS usage_records_metric_type_check;

ALTER TABLE public.usage_records
  ADD CONSTRAINT usage_records_metric_type_check
  CHECK (metric_type IN (
    'workflow_runs',
    'ai_tokens',
    'outputs',
    'api_calls',
    'research_lookups',
    'voice_minutes'
  ));

-- 4) Plan allotments + overage (flagged for review; mechanism ships)
-- Node 60 / Control 300 / Command 1200 minutes; overage $0.12/min
UPDATE public.billing_plans
SET
  features = COALESCE(features, '{}'::jsonb) || '{"voice_minutes_per_month": 60}'::jsonb,
  overage_rates = COALESCE(overage_rates, '{}'::jsonb) || '{"voice_minute": 0.12}'::jsonb
WHERE lower(code) IN ('node', 'starter', 'free');

UPDATE public.billing_plans
SET
  features = COALESCE(features, '{}'::jsonb) || '{"voice_minutes_per_month": 300}'::jsonb,
  overage_rates = COALESCE(overage_rates, '{}'::jsonb) || '{"voice_minute": 0.12}'::jsonb
WHERE lower(code) IN ('control', 'growth');

UPDATE public.billing_plans
SET
  features = COALESCE(features, '{}'::jsonb) || '{"voice_minutes_per_month": 1200}'::jsonb,
  overage_rates = COALESCE(overage_rates, '{}'::jsonb) || '{"voice_minute": 0.12}'::jsonb
WHERE lower(code) IN ('command', 'scale', 'enterprise');

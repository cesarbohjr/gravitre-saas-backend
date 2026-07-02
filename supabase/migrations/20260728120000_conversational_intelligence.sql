-- Conversational intelligence layer: task state, persona preference, dialogue settings

ALTER TABLE public.conversations
  ADD COLUMN IF NOT EXISTS task_state jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.user_preferences
  ADD COLUMN IF NOT EXISTS preferred_persona text;

ALTER TABLE public.org_intelligence_engine_settings
  ADD COLUMN IF NOT EXISTS dialogue_settings jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS default_persona text DEFAULT 'friendly_assistant';

CREATE INDEX IF NOT EXISTS idx_conversations_task_state_gin
  ON public.conversations USING gin (task_state);

COMMENT ON COLUMN public.conversations.task_state IS
  'Structured multi-turn task state: clarified params, plan progress, rejected options.';

COMMENT ON COLUMN public.user_preferences.preferred_persona IS
  'Communication-style persona key (distinct from agent capability personas).';

COMMENT ON COLUMN public.org_intelligence_engine_settings.dialogue_settings IS
  'Org-level chat dialogue policy: clarification thresholds, proactive suggestions, consensus.';

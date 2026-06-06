-- STA-99: Wire fine-tuned models to agent runtime

ALTER TABLE public.agents
  ADD COLUMN IF NOT EXISTS trained_model_id uuid REFERENCES public.trained_models(id) ON DELETE SET NULL;

ALTER TABLE public.training_jobs
  ADD COLUMN IF NOT EXISTS trained_model_id uuid REFERENCES public.trained_models(id) ON DELETE SET NULL;

ALTER TABLE public.model_calls
  ADD COLUMN IF NOT EXISTS agent_id uuid REFERENCES public.agents(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS trained_model_id uuid REFERENCES public.trained_models(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS trained_model_version integer,
  ADD COLUMN IF NOT EXISTS used_fallback boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_agents_trained_model ON public.agents(trained_model_id)
  WHERE trained_model_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_model_calls_agent ON public.model_calls(org_id, agent_id, created_at DESC);

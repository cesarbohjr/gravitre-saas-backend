-- Resolve the ai_usage naming gap: model_calls is the canonical AI-spend table
-- (completions + embeddings). Expose it under the spec name `ai_usage` as a
-- read-only view. security_invoker=true so the querying user's RLS on
-- model_calls applies (tenant isolation is preserved).

CREATE OR REPLACE VIEW public.ai_usage
  WITH (security_invoker = true)
AS
SELECT
  id,
  org_id,
  task_type,
  provider,
  model_name,
  input_tokens,
  output_tokens,
  latency_ms,
  cost_usd,
  cache_hit,
  created_at
FROM public.model_calls;

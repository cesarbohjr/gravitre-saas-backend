-- Phase 5: SQL percentiles for metrics performance

CREATE OR REPLACE FUNCTION public.metrics_rag_latency_p95(org_id uuid, start_at timestamptz)
RETURNS numeric
LANGUAGE sql
STABLE
AS $$
  SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
  FROM public.rag_retrieval_logs
  WHERE org_id = $1
    AND created_at >= $2
    AND latency_ms IS NOT NULL;
$$;

CREATE OR REPLACE FUNCTION public.metrics_exec_duration_p95(org_id uuid, start_at timestamptz)
RETURNS numeric
LANGUAGE sql
STABLE
AS $$
  SELECT percentile_cont(0.95)
  WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - created_at)) * 1000)
  FROM public.workflow_runs
  WHERE org_id = $1
    AND run_type = 'execute'
    AND created_at >= $2
    AND completed_at IS NOT NULL;
$$;

CREATE OR REPLACE FUNCTION public.metrics_ingest_chunks_p95(org_id uuid, start_at timestamptz)
RETURNS numeric
LANGUAGE sql
STABLE
AS $$
  SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY chunk_count)
  FROM public.rag_ingest_jobs
  WHERE org_id = $1
    AND created_at >= $2
    AND chunk_count IS NOT NULL;
$$;

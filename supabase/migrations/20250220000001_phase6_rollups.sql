-- Phase 6: Daily rollups and retention helpers

CREATE TABLE public.audit_events_daily (
  id bigserial PRIMARY KEY,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  day date NOT NULL,
  action text NOT NULL,
  count int NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, day, action)
);

CREATE INDEX idx_audit_events_daily_org_day ON public.audit_events_daily(org_id, day DESC);

CREATE TABLE public.workflow_runs_daily (
  id bigserial PRIMARY KEY,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  day date NOT NULL,
  run_type text NOT NULL,
  status text NOT NULL,
  count int NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, day, run_type, status)
);

CREATE INDEX idx_workflow_runs_daily_org_day ON public.workflow_runs_daily(org_id, day DESC);

CREATE TABLE public.connector_sends_daily (
  id bigserial PRIMARY KEY,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  day date NOT NULL,
  connector_type text NOT NULL,
  status text NOT NULL,
  count int NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, day, connector_type, status)
);

CREATE INDEX idx_connector_sends_daily_org_day ON public.connector_sends_daily(org_id, day DESC);

CREATE TABLE public.rag_retrieval_daily (
  id bigserial PRIMARY KEY,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  day date NOT NULL,
  total int NOT NULL,
  avg_latency_ms numeric NOT NULL,
  p95_latency_ms numeric NOT NULL,
  avg_result_count numeric NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, day)
);

CREATE INDEX idx_rag_retrieval_daily_org_day ON public.rag_retrieval_daily(org_id, day DESC);

ALTER TABLE public.audit_events_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_runs_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.connector_sends_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rag_retrieval_daily ENABLE ROW LEVEL SECURITY;

CREATE POLICY "audit_events_daily_org"
  ON public.audit_events_daily FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "workflow_runs_daily_org"
  ON public.workflow_runs_daily FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "connector_sends_daily_org"
  ON public.connector_sends_daily FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "rag_retrieval_daily_org"
  ON public.rag_retrieval_daily FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE OR REPLACE FUNCTION public.rollup_audit_events_daily(start_at timestamptz, end_at timestamptz)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO public.audit_events_daily (org_id, day, action, count)
  SELECT org_id, date(created_at), action, COUNT(*)
  FROM public.audit_events
  WHERE created_at >= start_at AND created_at < end_at
  GROUP BY org_id, date(created_at), action
  ON CONFLICT (org_id, day, action) DO UPDATE
    SET count = EXCLUDED.count;
END;
$$;

CREATE OR REPLACE FUNCTION public.rollup_workflow_runs_daily(start_at timestamptz, end_at timestamptz)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO public.workflow_runs_daily (org_id, day, run_type, status, count)
  SELECT org_id, date(created_at), run_type, status, COUNT(*)
  FROM public.workflow_runs
  WHERE created_at >= start_at AND created_at < end_at
  GROUP BY org_id, date(created_at), run_type, status
  ON CONFLICT (org_id, day, run_type, status) DO UPDATE
    SET count = EXCLUDED.count;
END;
$$;

CREATE OR REPLACE FUNCTION public.rollup_connector_sends_daily(start_at timestamptz, end_at timestamptz)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO public.connector_sends_daily (org_id, day, connector_type, status, count)
  SELECT org_id, date(created_at),
    CASE
      WHEN action LIKE 'slack.send.%' THEN 'slack'
      WHEN action LIKE 'email.send.%' THEN 'email'
      WHEN action LIKE 'webhook.send.%' THEN 'webhook'
      ELSE 'unknown'
    END AS connector_type,
    CASE
      WHEN action LIKE '%.sent' THEN 'sent'
      WHEN action LIKE '%.failed' THEN 'failed'
      ELSE 'unknown'
    END AS status,
    COUNT(*)
  FROM public.audit_events
  WHERE created_at >= start_at AND created_at < end_at
    AND action IN ('slack.send.sent','slack.send.failed','email.send.sent','email.send.failed','webhook.send.sent','webhook.send.failed')
  GROUP BY org_id, date(created_at), connector_type, status
  ON CONFLICT (org_id, day, connector_type, status) DO UPDATE
    SET count = EXCLUDED.count;
END;
$$;

CREATE OR REPLACE FUNCTION public.rollup_rag_retrieval_daily(start_at timestamptz, end_at timestamptz)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO public.rag_retrieval_daily (org_id, day, total, avg_latency_ms, p95_latency_ms, avg_result_count)
  SELECT org_id,
         date(created_at),
         COUNT(*),
         COALESCE(AVG(latency_ms), 0),
         COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0),
         COALESCE(AVG(result_count), 0)
  FROM public.rag_retrieval_logs
  WHERE created_at >= start_at AND created_at < end_at
  GROUP BY org_id, date(created_at)
  ON CONFLICT (org_id, day) DO UPDATE
    SET total = EXCLUDED.total,
        avg_latency_ms = EXCLUDED.avg_latency_ms,
        p95_latency_ms = EXCLUDED.p95_latency_ms,
        avg_result_count = EXCLUDED.avg_result_count;
END;
$$;

CREATE OR REPLACE FUNCTION public.rollup_all_daily(start_at timestamptz, end_at timestamptz)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM public.rollup_audit_events_daily(start_at, end_at);
  PERFORM public.rollup_workflow_runs_daily(start_at, end_at);
  PERFORM public.rollup_connector_sends_daily(start_at, end_at);
  PERFORM public.rollup_rag_retrieval_daily(start_at, end_at);
END;
$$;

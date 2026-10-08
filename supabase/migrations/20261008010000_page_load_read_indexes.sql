-- Page-load performance (2026-10-08): indexes for two org-scoped reads that
-- every Home / Intelligence load triggers and that no existing index serves.
--
-- 1. Business-signal priorities read the latest work_object_events per org:
--      WHERE org_id = $1 ORDER BY created_at DESC LIMIT 1500
--    idx_work_object_events_org_object_created is (org_id, work_object_id,
--    created_at) and cannot serve an org-wide ORDER BY created_at.
CREATE INDEX IF NOT EXISTS idx_work_object_events_org_created
  ON public.work_object_events (org_id, created_at DESC);

-- 2. The daily briefing counts completed agent jobs in the last 24h:
--      WHERE org_id = $1 AND status = 'completed' AND finished_at >= $2
--    Only (org_id, created_at) and (status, created_at) existed.
CREATE INDEX IF NOT EXISTS idx_agent_jobs_org_status_finished
  ON public.agent_jobs (org_id, status, finished_at DESC);

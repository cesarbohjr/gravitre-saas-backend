-- Covering index for action-filtered audit queries
-- (golden_signals / metrics / routers/audit: org_id + action + created_at).
CREATE INDEX IF NOT EXISTS idx_audit_events_org_action_created
  ON public.audit_events (org_id, action, created_at DESC);

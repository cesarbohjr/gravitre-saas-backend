-- Enable RLS on billing usage tables
-- These tables were created without RLS in
-- 20260531000000_activate_billing_tables.sql
-- Service role bypasses RLS (backend writes are safe)
-- Authenticated users can read only their own org

ALTER TABLE usage_tracking
  ENABLE ROW LEVEL SECURITY;

ALTER TABLE overage_usage
  ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_isolation_usage_tracking"
  ON usage_tracking
  FOR SELECT
  USING (
    org_id IN (
      SELECT org_id
      FROM organization_members
      WHERE user_id = auth.uid()
    )
  );

CREATE POLICY "tenant_isolation_overage_usage"
  ON overage_usage
  FOR SELECT
  USING (
    org_id IN (
      SELECT org_id
      FROM organization_members
      WHERE user_id = auth.uid()
    )
  );

-- No INSERT/UPDATE/DELETE policies for authenticated users.
-- All writes come from the service role only.

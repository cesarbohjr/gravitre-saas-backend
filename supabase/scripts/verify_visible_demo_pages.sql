-- Verify data required for visible demo pages
-- Target org: 00000000-0000-0000-0000-000000000001

WITH target_org AS (
  SELECT '00000000-0000-0000-0000-000000000001'::uuid AS org_id
),
agents_count AS (
  SELECT COUNT(*)::int AS count
  FROM public.agents a, target_org o
  WHERE a.org_id = o.org_id
),
workflows_count AS (
  SELECT COUNT(*)::int AS count
  FROM public.workflows w, target_org o
  WHERE w.org_id = o.org_id
),
runs_count AS (
  SELECT COUNT(*)::int AS count
  FROM public.runs r, target_org o
  WHERE r.org_id = o.org_id
),
approvals_count AS (
  SELECT COUNT(*)::int AS count
  FROM public.approvals ap, target_org o
  WHERE ap.org_id = o.org_id
),
operator_visible_count AS (
  SELECT COUNT(*)::int AS count
  FROM public.runs r, target_org o
  WHERE r.org_id = o.org_id
    AND (
      r.status IN ('running', 'pending') -- queued maps to pending
      OR r.approval_status = 'pending'   -- needs_approval
    )
),
organization_exists AS (
  SELECT COUNT(*)::int AS count
  FROM public.organizations org, target_org o
  WHERE org.id = o.org_id
)
SELECT 'agents_count' AS check_name, count AS value, (count > 0) AS pass FROM agents_count
UNION ALL
SELECT 'workflows_count' AS check_name, count AS value, (count > 0) AS pass FROM workflows_count
UNION ALL
SELECT 'runs_count' AS check_name, count AS value, (count > 0) AS pass FROM runs_count
UNION ALL
SELECT 'approvals_count' AS check_name, count AS value, (count > 0) AS pass FROM approvals_count
UNION ALL
SELECT 'operator_query_count' AS check_name, count AS value, (count > 0) AS pass FROM operator_visible_count
UNION ALL
SELECT 'settings_organization_exists' AS check_name, count AS value, (count > 0) AS pass FROM organization_exists
ORDER BY check_name;

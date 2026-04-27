-- ============================================================
-- Verify Cohesive Demo Seed (Acme Corp)
-- ============================================================
-- Validates counts and integrity for:
-- org_id = 00000000-0000-0000-0000-000000000001

WITH constants AS (
  SELECT '00000000-0000-0000-0000-000000000001'::uuid AS demo_org_id
)
SELECT 'organizations' AS entity, COUNT(*)::bigint AS row_count
FROM public.organizations o, constants c
WHERE o.id = c.demo_org_id
UNION ALL
SELECT 'users', COUNT(*)::bigint
FROM public.users u, constants c
WHERE u.org_id = c.demo_org_id
UNION ALL
SELECT 'organization_members', COUNT(*)::bigint
FROM public.organization_members om, constants c
WHERE om.org_id = c.demo_org_id
UNION ALL
SELECT 'agents', COUNT(*)::bigint
FROM public.agents a, constants c
WHERE a.org_id = c.demo_org_id
UNION ALL
SELECT 'workflows', COUNT(*)::bigint
FROM public.workflows w, constants c
WHERE w.org_id = c.demo_org_id
UNION ALL
SELECT 'runs', COUNT(*)::bigint
FROM public.runs r, constants c
WHERE r.org_id = c.demo_org_id
UNION ALL
SELECT 'run_steps', COUNT(*)::bigint
FROM public.run_steps rs, constants c
WHERE rs.org_id = c.demo_org_id
UNION ALL
SELECT 'approvals', COUNT(*)::bigint
FROM public.approvals a, constants c
WHERE a.org_id = c.demo_org_id
UNION ALL
SELECT 'connected_systems', COUNT(*)::bigint
FROM public.connected_systems cs, constants c
WHERE cs.org_id = c.demo_org_id
UNION ALL
SELECT 'goals', CASE WHEN to_regclass('public.goals') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint FROM public.goals g, constants c WHERE g.org_id = c.demo_org_id
) END
UNION ALL
SELECT 'goal_plans', CASE WHEN to_regclass('public.goal_plans') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint FROM public.goal_plans gp, constants c WHERE gp.org_id = c.demo_org_id
) END
UNION ALL
SELECT 'council_sessions', CASE WHEN to_regclass('public.council_sessions') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint FROM public.council_sessions cs, constants c WHERE cs.org_id = c.demo_org_id
) END
UNION ALL
SELECT 'council_contributions', CASE WHEN to_regclass('public.council_contributions') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint FROM public.council_contributions cc, constants c WHERE cc.org_id = c.demo_org_id
) END
UNION ALL
SELECT 'workflow_health_snapshots', CASE WHEN to_regclass('public.workflow_health_snapshots') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint FROM public.workflow_health_snapshots whs, constants c WHERE whs.org_id = c.demo_org_id
) END
UNION ALL
SELECT 'optimization_recommendations', CASE WHEN to_regclass('public.optimization_recommendations') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint FROM public.optimization_recommendations o, constants c WHERE o.org_id = c.demo_org_id
) END
UNION ALL
SELECT 'workflow_ab_tests', CASE WHEN to_regclass('public.workflow_ab_tests') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint FROM public.workflow_ab_tests w, constants c WHERE w.org_id = c.demo_org_id
) END
UNION ALL
SELECT 'model_settings', COUNT(*)::bigint
FROM public.model_settings ms, constants c
WHERE ms.org_id = c.demo_org_id
ORDER BY entity;

-- 1) Verify all org-scoped rows use demo org (should be 0 for each non_demo_count)
WITH constants AS (
  SELECT '00000000-0000-0000-0000-000000000001'::uuid AS demo_org_id
)
SELECT 'users' AS entity, COUNT(*)::bigint AS non_demo_count
FROM public.users u, constants c
WHERE u.org_id <> c.demo_org_id
UNION ALL
SELECT 'agents', COUNT(*)::bigint
FROM public.agents a, constants c
WHERE a.org_id <> c.demo_org_id
UNION ALL
SELECT 'workflows', COUNT(*)::bigint
FROM public.workflows w, constants c
WHERE w.org_id <> c.demo_org_id
UNION ALL
SELECT 'runs', COUNT(*)::bigint
FROM public.runs r, constants c
WHERE r.org_id <> c.demo_org_id
UNION ALL
SELECT 'run_steps', COUNT(*)::bigint
FROM public.run_steps rs, constants c
WHERE rs.org_id <> c.demo_org_id
UNION ALL
SELECT 'approvals', COUNT(*)::bigint
FROM public.approvals a, constants c
WHERE a.org_id <> c.demo_org_id
UNION ALL
SELECT 'connected_systems', COUNT(*)::bigint
FROM public.connected_systems cs, constants c
WHERE cs.org_id <> c.demo_org_id
UNION ALL
SELECT 'goals', CASE WHEN to_regclass('public.goals') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint FROM public.goals g, constants c WHERE g.org_id <> c.demo_org_id
) END
UNION ALL
SELECT 'goal_plans', CASE WHEN to_regclass('public.goal_plans') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint FROM public.goal_plans gp, constants c WHERE gp.org_id <> c.demo_org_id
) END
UNION ALL
SELECT 'council_sessions', CASE WHEN to_regclass('public.council_sessions') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint FROM public.council_sessions cs, constants c WHERE cs.org_id <> c.demo_org_id
) END
UNION ALL
SELECT 'council_contributions', CASE WHEN to_regclass('public.council_contributions') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint FROM public.council_contributions cc, constants c WHERE cc.org_id <> c.demo_org_id
) END
UNION ALL
SELECT 'workflow_health_snapshots', CASE WHEN to_regclass('public.workflow_health_snapshots') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint FROM public.workflow_health_snapshots whs, constants c WHERE whs.org_id <> c.demo_org_id
) END
UNION ALL
SELECT 'optimization_recommendations', CASE WHEN to_regclass('public.optimization_recommendations') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint FROM public.optimization_recommendations o, constants c WHERE o.org_id <> c.demo_org_id
) END
UNION ALL
SELECT 'workflow_ab_tests', CASE WHEN to_regclass('public.workflow_ab_tests') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint FROM public.workflow_ab_tests w, constants c WHERE w.org_id <> c.demo_org_id
) END
UNION ALL
SELECT 'model_settings', COUNT(*)::bigint
FROM public.model_settings ms, constants c
WHERE ms.org_id <> c.demo_org_id
ORDER BY entity;

-- 2) No orphan runs (runs.workflow_id should reference workflows when present)
SELECT COUNT(*)::bigint AS orphan_runs
FROM public.runs r
LEFT JOIN public.workflows w ON w.id = r.workflow_id
WHERE r.workflow_id IS NOT NULL
  AND w.id IS NULL;

-- 3) No orphan run_steps
SELECT COUNT(*)::bigint AS orphan_run_steps
FROM public.run_steps rs
LEFT JOIN public.runs r ON r.id = rs.run_id
WHERE r.id IS NULL;

-- 4) No approvals without runs
SELECT COUNT(*)::bigint AS approvals_without_runs
FROM public.approvals a
LEFT JOIN public.runs r ON r.id = a.run_id
WHERE a.run_id IS NULL OR r.id IS NULL;

-- 5) No goal_plans without goals
SELECT CASE WHEN to_regclass('public.goal_plans') IS NULL OR to_regclass('public.goals') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint
  FROM public.goal_plans gp
  LEFT JOIN public.goals g ON g.id = gp.goal_id
  WHERE gp.goal_id IS NULL OR g.id IS NULL
) END AS goal_plans_without_goals;

-- 6) No recommendations without workflows
SELECT CASE WHEN to_regclass('public.optimization_recommendations') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint
  FROM public.optimization_recommendations o
  LEFT JOIN public.workflows w ON w.id = o.workflow_id
  WHERE o.workflow_id IS NULL OR w.id IS NULL
) END AS recommendations_without_workflows;

-- 7) Operator query shape has at least one row
SELECT COUNT(*)::bigint AS operator_query_rows
FROM public.runs
WHERE org_id = '00000000-0000-0000-0000-000000000001'
  AND (
    status IN ('running', 'pending')
    OR approval_status = 'pending'
  );

-- 8) Agents referenced in councils exist
SELECT CASE WHEN to_regclass('public.council_contributions') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint
  FROM public.council_contributions cc
  LEFT JOIN public.agents a ON a.id = cc.agent_id
  WHERE cc.agent_id IS NOT NULL
    AND a.id IS NULL
) END AS missing_contribution_agent_refs;

SELECT CASE WHEN to_regclass('public.council_sessions') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint
  FROM public.council_sessions cs
  CROSS JOIN LATERAL jsonb_array_elements(cs.participating_agents) agent_item
  LEFT JOIN public.agents a
    ON a.id = (
      CASE
        WHEN (agent_item->>'id') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        THEN (agent_item->>'id')::uuid
        ELSE NULL
      END
    )
  WHERE (agent_item->>'id') IS NOT NULL
    AND a.id IS NULL
) END AS missing_session_agent_refs;

-- 9) Workflow refs in health/recommendations exist
SELECT CASE WHEN to_regclass('public.workflow_health_snapshots') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint
  FROM public.workflow_health_snapshots whs
  LEFT JOIN public.workflows w ON w.id = whs.workflow_id
  WHERE whs.workflow_id IS NOT NULL
    AND w.id IS NULL
) END AS missing_health_workflow_refs;

SELECT CASE WHEN to_regclass('public.optimization_recommendations') IS NULL THEN 0 ELSE (
  SELECT COUNT(*)::bigint
  FROM public.optimization_recommendations o
  LEFT JOIN public.workflows w ON w.id = o.workflow_id
  WHERE o.workflow_id IS NOT NULL
    AND w.id IS NULL
) END AS missing_recommendation_workflow_refs;

-- Optional table presence report for feature gaps
SELECT
  to_regclass('public.reports') IS NOT NULL AS reports_table_exists,
  to_regclass('public.insights') IS NOT NULL AS insights_table_exists,
  to_regclass('public.notifications') IS NOT NULL AS notifications_table_exists,
  to_regclass('public.team_settings') IS NOT NULL AS team_settings_table_exists;

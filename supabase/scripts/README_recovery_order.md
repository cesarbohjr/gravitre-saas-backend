# Supabase Recovery Runbook (Gravitre)

This is the canonical restart order for this repository.

Use this when rebuilding/resetting demo data for production-style UI checks.

## 1) Run these migrations in SQL Editor (in order)

1. `supabase/migrations/20260424_gravitre_frontend_contract_schema.sql`
2. `supabase/migrations/20260426_goal_based_workflows.sql`
3. `supabase/migrations/20260426_agent_council.sql`
4. `supabase/migrations/20260426_workflow_optimization.sql`
5. `supabase/migrations/20260427000100_billing_events_demo.sql`

## 2) Seed data (in order)

1. `supabase/scripts/seed_demo_cohesive_data.sql`
2. `supabase/scripts/seed_demo_cohesive_data_org2.sql` (optional but recommended)

## 3) Verification scripts (in order)

1. `supabase/scripts/verify_visible_demo_pages.sql`
2. `supabase/scripts/verify_demo_cohesive_data.sql`

## 4) Expected API checks after deploy

- `/api/agents?debug=1`
- `/api/workflows?debug=1`
- `/api/runs?debug=1`
- `/api/approvals?debug=1`
- `/api/settings/organization`
- `/api/runs?status=running,queued,needs_approval&debug=1`

## 5) Required Vercel environment variables

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

All three must be from the same Supabase project.

## Deprecated/legacy files

Confusing old SQL files have been moved to:

- `supabase/scripts/legacy/`
- `supabase/migrations/legacy/`

Do not use those for standard recovery.

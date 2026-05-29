-- Per-org override for the hard AI-budget gate.
--
-- NULL  -> inherit the global AI_HARD_BUDGET_ENABLED flag (default behavior)
-- true  -> force the budget gate ON for this org (even if global is off)
-- false -> force the budget gate OFF for this org (even if global is on)
--
-- Lets enforcement be staged per-tenant (enable for specific orgs first) while
-- the global flag stays off. Safe to re-run.

ALTER TABLE public.org_billing
  ADD COLUMN IF NOT EXISTS hard_budget_enabled boolean;

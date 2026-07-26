/**
 * Canonical plan limits — must match public.billing_plans seed
 * (migration 20260729120000_seed_all_billing_plans.sql +
 * 20260719120000_billing_plans_research_lookups.sql).
 */
export const PLAN_LIMITS = {
  node: {
    aiCredits: 1000,
    workflowRuns: 500,
    outputs: 10,
    outputOverageUsd: 2.5,
    mesonOverageUsd: null as number | null,
    researchLookups: 10,
  },
  control: {
    aiCredits: 5000,
    workflowRuns: 2500,
    outputs: 40,
    outputOverageUsd: 2.0,
    mesonOverageUsd: 3.0,
    researchLookups: 60,
  },
  command: {
    aiCredits: 15000,
    workflowRuns: 10000,
    outputs: 120,
    outputOverageUsd: 1.5,
    mesonOverageUsd: 2.0,
    researchLookups: 200,
  },
  enterprise: {
    aiCredits: 0,
    workflowRuns: 0,
    outputs: null as number | null,
    outputOverageUsd: null as number | null,
    mesonOverageUsd: null as number | null,
    researchLookups: 200,
  },
  free: {
    aiCredits: 0,
    workflowRuns: 200,
    outputs: 0,
    outputOverageUsd: 2.5,
    mesonOverageUsd: null as number | null,
    researchLookups: 0,
  },
} as const

export type PlanLimitCode = keyof typeof PLAN_LIMITS

export function planLimitsFor(code: string | null | undefined) {
  const key = (code ?? "node").toLowerCase() as PlanLimitCode
  return PLAN_LIMITS[key in PLAN_LIMITS ? key : "node"]
}

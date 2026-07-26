/**
 * Research Lookups pricing — must match public.billing_plans seed:
 * features.research_lookups_per_month + overage_rates.research_lookup
 * (migration 20260719120000_billing_plans_research_lookups.sql)
 */
export const RESEARCH_LOOKUP_OVERAGE_USD = 0.35

export const RESEARCH_LOOKUPS_INCLUDED_BY_PLAN = {
  node: 10,
  control: 60,
  command: 200,
  enterprise: 200,
} as const

export type ResearchLookupPlanCode = keyof typeof RESEARCH_LOOKUPS_INCLUDED_BY_PLAN

export function researchLookupsIncludedLabel(planCode: string): string {
  const count = RESEARCH_LOOKUPS_INCLUDED_BY_PLAN[planCode as ResearchLookupPlanCode]
  if (!count) return ""
  return `${count} research lookups included / month`
}

export function formatResearchLookupOveragePrice(): string {
  return `$${RESEARCH_LOOKUP_OVERAGE_USD.toFixed(2)} each`
}

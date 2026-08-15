import { Zap, Sliders, Crown, Rocket, Sparkles, type LucideIcon } from "lucide-react"

import { researchLookupsIncludedLabel } from "@/lib/internet-research-pricing"

// Single source of truth for subscription plans

export type PlanCode = "free" | "node" | "control" | "command" | "enterprise"

export type BillingInterval = "monthly" | "annual"

export type Plan = {
  code: PlanCode
  name: string
  /** Monthly price in USD. null = not publicly priced (free / custom enterprise). */
  price: number | null
  /**
   * Effective per-month price in USD when billed annually (mirrors the public
   * pricing page). null = not publicly priced (free / custom enterprise).
   */
  annualPrice: number | null
  tagline: string
  features: string[]
  icon: LucideIcon
  /** Whether this plan is offered for self-serve checkout. */
  selectable: boolean
  popular?: boolean
}

export const PLAN_CATALOG: Record<PlanCode, Plan> = {
  free: {
    code: "free",
    name: "Free",
    price: 0,
    annualPrice: 0,
    tagline: "Explore the basics",
    features: ["1 workflow", "Community support", "Limited runs"],
    icon: Sparkles,
    selectable: false,
  },
  node: {
    code: "node",
    name: "Node",
    price: 59,
    annualPrice: 49,
    tagline: "For individual operators",
    features: [
      "1 core user",
      "10 workflows",
      "Voice included (Text | Voice)",
      "Essential connectors",
      researchLookupsIncludedLabel("node"),
    ].filter(Boolean),
    icon: Zap,
    selectable: true,
  },
  control: {
    code: "control",
    name: "Control",
    price: 149,
    annualPrice: 124,
    tagline: "For growing teams",
    features: [
      "5 lite seats",
      "Meson builder",
      "Voice included (Text | Voice)",
      "Advanced connectors",
      researchLookupsIncludedLabel("control"),
    ].filter(Boolean),
    icon: Sliders,
    selectable: true,
    popular: true,
  },
  command: {
    code: "command",
    name: "Command",
    price: 349,
    annualPrice: 291,
    tagline: "For scaling organizations",
    features: [
      "Unlimited lite seats",
      "SSO & API access",
      "120 workflows",
      "Voice included (Text | Voice)",
      researchLookupsIncludedLabel("command"),
    ].filter(Boolean),
    icon: Crown,
    selectable: true,
  },
  enterprise: {
    code: "enterprise",
    name: "Enterprise",
    price: null,
    annualPrice: null,
    tagline: "For large deployments",
    features: ["Custom seats", "Dedicated support", "Custom security review", "200 research lookups included / month"],
    icon: Rocket,
    selectable: false,
  },
}

/** Plans shown in self-serve checkout / upgrade surfaces, in display order. */
export const SELECTABLE_PLANS: Plan[] = [
  PLAN_CATALOG.node,
  PLAN_CATALOG.control,
  PLAN_CATALOG.command,
]

/** Rank for comparing tiers (upgrade vs. downgrade vs. current). */
const PLAN_RANK: Record<PlanCode, number> = {
  free: 0,
  node: 1,
  control: 2,
  command: 3,
  enterprise: 4,
}

export function getPlan(code: string | null | undefined): Plan {
  if (code && code in PLAN_CATALOG) return PLAN_CATALOG[code as PlanCode]
  return PLAN_CATALOG.node
}

/** Effective per-month price for the given billing interval. */
export function planPriceForInterval(plan: Plan, interval: BillingInterval = "monthly"): number | null {
  return interval === "annual" ? plan.annualPrice : plan.price
}

export function formatPlanPrice(plan: Plan, interval: BillingInterval = "monthly"): string {
  const price = planPriceForInterval(plan, interval)
  if (price === null) return "Custom"
  if (price === 0) return "$0"
  return `$${price}`
}

/**
 * Price label for the subscriber's actual Stripe Price (grandfathered vs list).
 * Falls back to catalog list price when live cents are unavailable.
 */
export function formatChargedPlanPriceLabel(
  plan: Plan,
  unitAmountCents?: number | null,
  billingInterval?: string | null,
): string {
  if (typeof unitAmountCents === "number" && unitAmountCents > 0) {
    const interval = (billingInterval || "month").toLowerCase()
    const amountUsd =
      interval === "year"
        ? Math.round(unitAmountCents / 100 / 12)
        : Math.round(unitAmountCents / 100)
    return `$${amountUsd}`
  }
  return formatPlanPrice(plan)
}

/** Total charged once per year when billed annually (per-month rate × 12). */
export function annualBilledTotal(plan: Plan): number | null {
  if (plan.annualPrice === null || plan.annualPrice === 0) return plan.annualPrice
  return plan.annualPrice * 12
}

/** Yearly savings vs. paying monthly, or 0 when not applicable. */
export function annualSavings(plan: Plan): number {
  if (plan.price === null || plan.annualPrice === null) return 0
  return Math.max(0, (plan.price - plan.annualPrice) * 12)
}

/** "upgrade" | "downgrade" | "current" relative to the active tier. */
export function planDirection(target: PlanCode, current: PlanCode): "upgrade" | "downgrade" | "current" {
  if (PLAN_RANK[target] === PLAN_RANK[current]) return "current"
  return PLAN_RANK[target] > PLAN_RANK[current] ? "upgrade" : "downgrade"
}

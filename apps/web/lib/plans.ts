import { Zap, Sliders, Crown, Rocket, Sparkles, type LucideIcon } from "lucide-react"

// Single source of truth for subscription plans, keyed by the tier code the
// backend uses (see backend/app/billing/service.py DEFAULT_PLANS and the
// SubscriptionTier type). Both the billing page and the trial UpgradeModal read
// from here so plan names, prices, and feature bullets never drift apart.

export type PlanCode = "free" | "node" | "control" | "command" | "enterprise"

export type Plan = {
  code: PlanCode
  name: string
  /** Monthly price in USD. null = not publicly priced (free / custom enterprise). */
  price: number | null
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
    tagline: "Explore the basics",
    features: ["1 workflow", "Community support", "Limited runs"],
    icon: Sparkles,
    selectable: false,
  },
  node: {
    code: "node",
    name: "Node",
    price: 49,
    tagline: "For individual operators",
    features: ["1 core user", "10 workflows", "Essential connectors"],
    icon: Zap,
    selectable: true,
  },
  control: {
    code: "control",
    name: "Control",
    price: 129,
    tagline: "For growing teams",
    features: ["5 lite seats", "Meson builder", "Advanced connectors"],
    icon: Sliders,
    selectable: true,
    popular: true,
  },
  command: {
    code: "command",
    name: "Command",
    price: 299,
    tagline: "For scaling organizations",
    features: ["25 lite seats", "SSO & API access", "Unlimited workflows"],
    icon: Crown,
    selectable: true,
  },
  enterprise: {
    code: "enterprise",
    name: "Enterprise",
    price: null,
    tagline: "For large deployments",
    features: ["Custom seats", "Dedicated support", "Custom security review"],
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

export function formatPlanPrice(plan: Plan): string {
  if (plan.price === null) return "Custom"
  if (plan.price === 0) return "$0"
  return `$${plan.price}`
}

/** "upgrade" | "downgrade" | "current" relative to the active tier. */
export function planDirection(target: PlanCode, current: PlanCode): "upgrade" | "downgrade" | "current" {
  if (PLAN_RANK[target] === PLAN_RANK[current]) return "current"
  return PLAN_RANK[target] > PLAN_RANK[current] ? "upgrade" : "downgrade"
}

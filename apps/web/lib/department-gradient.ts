// Per-department identity accents shared by Agents and Marketplace.
// Glow is intentionally none — Extrovert / Emerald Intelligence uses
// compact identity, not glossy orbs (Figma page 03 agent studies).

export type DepartmentGradient = {
  /** Tailwind `from-*`/`to-*` classes for the orb's `bg-gradient-to-br`. */
  gradient: string
  /** Tailwind shadow color class for the orb's colored glow. */
  glow: string
  /** Tailwind `border-*` class for hover/active states that need the department hue. */
  border: string
}

const NONE = "shadow-none"
const TEAL: DepartmentGradient = { gradient: "from-teal-400 to-cyan-600", glow: NONE, border: "border-teal-500/60" }
const ROSE: DepartmentGradient = { gradient: "from-rose-400 to-pink-600", glow: NONE, border: "border-rose-500/60" }
const BLUE: DepartmentGradient = { gradient: "from-blue-400 to-indigo-600", glow: NONE, border: "border-blue-500/60" }
const AMBER: DepartmentGradient = { gradient: "from-amber-400 to-orange-600", glow: NONE, border: "border-amber-500/60" }
const VIOLET: DepartmentGradient = { gradient: "from-violet-400 to-fuchsia-600", glow: NONE, border: "border-violet-500/60" }
const EMERALD: DepartmentGradient = { gradient: "from-emerald-400 to-green-600", glow: NONE, border: "border-emerald-500/60" }
const SLATE: DepartmentGradient = { gradient: "from-slate-400 to-slate-600", glow: NONE, border: "border-slate-500/60" }

// Canonical department key -> gradient.
const GRADIENTS: Record<string, DepartmentGradient> = {
  customer_success: TEAL,
  support: TEAL,
  hr: ROSE,
  revenue_operations: BLUE,
  sales: BLUE,
  finance: EMERALD,
  operations: AMBER,
  marketing: VIOLET,
  legal: SLATE,
  engineering: BLUE,
  security: SLATE,
  general: BLUE,
}

// Normalizes the many department strings the backend can emit (e.g. "Customer
// Success", "RevOps", "MSP Operations", "People Ops") to a canonical key.
const ALIASES: Record<string, string> = {
  cs: "customer_success",
  customersuccess: "customer_success",
  customer_success: "customer_success",
  human_resources: "hr",
  people: "hr",
  people_ops: "hr",
  talent: "hr",
  hr_operations: "hr",
  revops: "revenue_operations",
  revenue: "revenue_operations",
  revenue_ops: "revenue_operations",
  sales_operations: "revenue_operations",
  accounting: "finance",
  billing: "finance",
  msp: "operations",
  msp_operations: "operations",
  it_operations: "operations",
  it: "operations",
  ops: "operations",
  marketing_operations: "marketing",
  growth: "marketing",
  demand: "marketing",
  compliance: "legal",
  counsel: "legal",
  developer: "engineering",
  platform: "engineering",
  infra: "engineering",
}

/** Resolves the department accent (gradient + border; glow is unused). */
export function departmentGradient(department: string | null | undefined): DepartmentGradient {
  const raw = (department ?? "").toLowerCase().trim().replace(/\s+/g, "_")
  if (!raw) return BLUE
  const key = ALIASES[raw] ?? raw
  return GRADIENTS[key] ?? BLUE
}
